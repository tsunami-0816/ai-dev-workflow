#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
step7.5 测试数据重置（项目专用，非通用 reset 脚本）

做四件事：
  1) 备份当前库（mysqldump）到 07_联调/evidence/
  2) TRUNCATE 业务表 → 重跑 db/init.sql 重建「2 账号 + 4 套餐」最小种子
  3) 清 Redis 本项目键（ub:pkg:list / ub:jwt:blacklist:* / ub:nonce:* / ub:idem:booking:*）
  4) 清 MQ 遗留消息（booking.notify.queue / booking.notify.dlq），避免消费到已删除预约

最后做机器断言：表计数、自增位、中文可回读（逐字比对，不靠人眼）、口令哈希非空。
任一断言失败 → exit 1，不写「可交接」。

用法：
  set MYSQL_PORT=3307 && python scripts/reset_test_data.py
  python scripts/reset_test_data.py --no-backup --no-mq
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_INIT_SQL = os.path.join(PROJECT_ROOT, "05_代码", "backend", "db", "init.sql")
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "07_联调", "evidence")

EXPECT_USERS = 2
EXPECT_PACKAGES = 4
EXPECT_BOOKINGS = 0
EXPECT_NOTIFY_LOGS = 0

EXPECT_USER_ROWS = [
    (1, "demo", None, "演示用户A"),
    (2, "demo2", None, "演示用户B"),
]
EXPECT_PACKAGE_ROWS = [
    (1, "城市轻写真", "399.00"),
    (2, "复古胶片", "499.00"),
    (3, "情侣纪实", "699.00"),
    (4, "个人写真·夜场", "599.00"),
]


class Runner:
    def __init__(self, log_path=None):
        self.lines = []
        self.log_path = log_path or os.path.join(EVIDENCE_DIR, "step7_5_reset.log")

    def say(self, msg=""):
        print(msg)
        self.lines.append(msg)

    def finish(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(self.lines) + "\n")


def find_mysql_client(name):
    env_bin = os.environ.get("MYSQL_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    candidate = os.path.join(os.path.dirname(os.environ.get("MYSQL_BIN", "")), name)
    if candidate and os.path.isfile(candidate):
        return candidate
    known = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\%s.exe" % name
    if os.path.isfile(known):
        return known
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit("找不到 %s，可用 MYSQL_BIN 指定完整路径" % name)


def mysql_run(sql, db=None, want_output=False, capture=True):
    """通过 mysql.exe 执行 SQL；capture=True 时返回 stdout 字节串。"""
    args = [
        find_mysql_client("mysql"),
        "-h", ARGS.mysql_host,
        "-P", str(ARGS.mysql_port),
        "-u", ARGS.mysql_user,
        "-p" + ARGS.mysql_password,
        "--default-character-set=utf8mb4",
        "--batch",
        "--raw",
        "--skip-column-names",
    ]
    if db:
        args += ["-D", db]
    proc = subprocess.run(
        args,
        input=sql.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "mysql 执行失败 rc=%d stderr=%s" % (proc.returncode, proc.stderr.decode("utf-8", "replace"))
        )
    return proc.stdout if capture else b""


def mysql_rows(sql, db):
    out = mysql_run(sql, db=db)
    text = out.decode("utf-8", "replace")
    rows = []
    for line in text.splitlines():
        if line.strip() == "":
            continue
        rows.append(line.split("\t"))
    return rows


def mysql_scalar(sql, db):
    rows = mysql_rows(sql, db)
    return rows[0][0] if rows else ""


class RespClient:
    """最小 RESP 客户端：只用到 AUTH/KEYS/DEL/PING/INFO，够清缓存即可。"""

    def __init__(self, host, port, password=None, timeout=3):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        if password:
            self.cmd("AUTH", password)

    def send(self, *parts):
        payload = b"*%d\r\n" % len(parts)
        for p in parts:
            b = str(p).encode("utf-8")
            payload += b"$%d\r\n%s\r\n" % (len(b), b)
        self.sock.sendall(payload)

    def read_reply(self):
        return self._read()

    def _read(self):
        raw = self._readline()
        if raw is None:
            raise ConnectionError("redis 连接被关闭")
        if raw.startswith(b"+"):
            return raw[1:].decode("utf-8", "replace")
        if raw.startswith(b"-"):
            raise RuntimeError("redis 错误: " + raw[1:].decode("utf-8", "replace"))
        if raw.startswith(b":"):
            return int(raw[1:])
        if raw.startswith(b"$"):
            n = int(raw[1:])
            if n == -1:
                return None
            data = self._read_exact(n)
            self._readline()  # 吃掉结尾 \r\n
            return data.decode("utf-8", "replace")
        if raw.startswith(b"*"):
            n = int(raw[1:])
            if n == -1:
                return None
            return [self._read() for _ in range(n)]
        raise RuntimeError("无法解析 RESP 应答: %r" % raw)

    def _readline(self):
        buf = b""
        while True:
            chunk = self.sock.recv(1)
            if not chunk:
                return None
            buf += chunk
            if buf.endswith(b"\r\n"):
                return buf[:-2]

    def _read_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("redis 连接提前关闭")
            buf += chunk
        return buf

    def cmd(self, *parts):
        self.send(*parts)
        return self.read_reply()


def redis_clear(runner):
    try:
        cli = RespClient(ARGS.redis_host, ARGS.redis_port, ARGS.redis_password)
    except Exception as ex:
        runner.say("  [WARN] Redis 连不上（%s:%s）：%s，跳过缓存清理" % (ARGS.redis_host, ARGS.redis_port, ex))
        return {"reachable": False, "deleted": 0, "keys": []}
    keys = cli.cmd("KEYS", "ub:*") or []
    deleted = 0
    if keys:
        deleted = int(cli.cmd("DEL", *keys))
    remain = cli.cmd("KEYS", "ub:*") or []
    runner.say("  Redis %s:%s：删除 %d 个本项目键（剩余 %d）" % (ARGS.redis_host, ARGS.redis_port, deleted, len(remain)))
    if keys:
        runner.say("  keys=" + ", ".join(sorted(keys)))
    return {"reachable": True, "deleted": deleted, "keys": list(keys), "remaining": list(remain)}


def mq_purge(runner):
    queues = ["booking.notify.queue", "booking.notify.dlq"]
    info = {}
    if not shutil.which("docker"):
        runner.say("  [WARN] 无 docker，跳过 MQ 清理")
        return {"purged": False, "reason": "no-docker"}
    for q in queues:
        try:
            before = subprocess.run(
                ["docker", "exec", "rag-rabbitmq", "rabbitmqctl", "list_queues", "name", "messages"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60, text=True, encoding="utf-8"
            )
            before_lines = [ln for ln in (before.stdout or "").splitlines() if ln.startswith(q)]
            subprocess.run(
                ["docker", "exec", "rag-rabbitmq", "rabbitmqctl", "purge_queue", q],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=True
            )
            after = subprocess.run(
                ["docker", "exec", "rag-rabbitmq", "rabbitmqctl", "list_queues", "name", "messages"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60, text=True, encoding="utf-8"
            )
            after_lines = [ln for ln in (after.stdout or "").splitlines() if ln.startswith(q)]
            info[q] = {"before": before_lines, "after": after_lines}
            runner.say("  MQ %s：%s → %s" % (q, before_lines[0] if before_lines else "(none)",
                                             after_lines[0] if after_lines else "(none)"))
        except Exception as ex:
            info[q] = {"error": str(ex)}
            runner.say("  [WARN] MQ %s 清理失败：%s" % (q, ex))
    return {"purged": True, "queues": info}


def backup(runner):
    if ARGS.no_backup:
        runner.say("  已指定 --no-backup，跳过备份")
        return None
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(EVIDENCE_DIR, "db_before_reset_%s.sql" % stamp)
    args = [
        find_mysql_client("mysqldump"),
        "-h", ARGS.mysql_host,
        "-P", str(ARGS.mysql_port),
        "-u", ARGS.mysql_user,
        "-p" + ARGS.mysql_password,
        "--default-character-set=utf8mb4",
        "--single-transaction",
        "--routines", "--events",
        "--databases", ARGS.mysql_db,
        "--result-file=" + path,
    ]
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError("mysqldump 失败: " + proc.stderr.decode("utf-8", "replace"))
    runner.say("  备份 → %s (%d bytes)" % (path, os.path.getsize(path)))
    return path


def counts(runner):
    rows = mysql_rows(
        "SELECT 'user',COUNT(*) FROM user UNION ALL SELECT 'package',COUNT(*) FROM package "
        "UNION ALL SELECT 'booking',COUNT(*) FROM booking UNION ALL SELECT 'notify_log',COUNT(*) FROM notify_log;",
        ARGS.mysql_db,
    )
    return {name: int(cnt) for name, cnt in rows}


def auto_increments():
    ddl = mysql_rows(
        "SELECT TABLE_NAME, AUTO_INCREMENT FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA='%s' AND TABLE_NAME IN ('user','package','booking','notify_log') ORDER BY TABLE_NAME;"
        % ARGS.mysql_db,
        ARGS.mysql_db,
    )
    return {name: int(v) for name, v in ddl}


def assert_all(runner):
    ok = True
    c = counts(runner)
    runner.say("  计数：user=%d package=%d booking=%d notify_log=%d"
               % (c.get("user", -1), c.get("package", -1), c.get("booking", -1), c.get("notify_log", -1)))
    expect = {"user": EXPECT_USERS, "package": EXPECT_PACKAGES, "booking": EXPECT_BOOKINGS, "notify_log": EXPECT_NOTIFY_LOGS}
    for k, v in expect.items():
        if c.get(k, -1) != v:
            ok = False
            runner.say("  [FAIL] %s 计数 %s != 期望 %s" % (k, c.get(k), v))

    ai = auto_increments()
    runner.say("  自增位：user=%s package=%s booking=%s notify_log=%s"
               % (ai.get("user"), ai.get("package"), ai.get("booking"), ai.get("notify_log")))
    for k, v in {"user": 3, "package": 5, "booking": 1, "notify_log": 1}.items():
        if ai.get(k) != v:
            ok = False
            runner.say("  [FAIL] %s AUTO_INCREMENT=%s != 期望 %s" % (k, ai.get(k), v))

    # 中文逐字比对（可回读，不靠肉眼）
    user_rows = mysql_rows("SELECT id,account,IFNULL(openid,'__NULL__'),nickname FROM user ORDER BY id;", ARGS.mysql_db)
    got_users = [(int(r[0]), r[1], None if r[2] == "__NULL__" else r[2], r[3]) for r in user_rows]
    runner.say("  账号回读：" + json.dumps(got_users, ensure_ascii=False))
    if got_users != EXPECT_USER_ROWS:
        ok = False
        runner.say("  [FAIL] 账号行与种子不一致（期望 %s）" % json.dumps(EXPECT_USER_ROWS, ensure_ascii=False))

    pkg_rows = mysql_rows("SELECT id,title,price FROM package ORDER BY id;", ARGS.mysql_db)
    got_pkgs = [(int(r[0]), r[1], r[2]) for r in pkg_rows]
    runner.say("  套餐回读：" + json.dumps(got_pkgs, ensure_ascii=False))
    if got_pkgs != EXPECT_PACKAGE_ROWS:
        ok = False
        runner.say("  [FAIL] 套餐行与种子不一致（期望 %s）" % json.dumps(EXPECT_PACKAGE_ROWS, ensure_ascii=False))

    # 说明文案中文可回读 + 口令哈希非空
    detail = mysql_rows("SELECT title,CHAR_LENGTH(summary),summary FROM package WHERE id=1;", ARGS.mysql_db)
    if detail:
        runner.say("  package#1 说明：chars=%s text=%s" % (detail[0][1], detail[0][2]))
        if "室内自然光棚拍" not in detail[0][2]:
            ok = False
            runner.say("  [FAIL] package#1 summary 中文回读异常")
    else:
        ok = False
        runner.say("  [FAIL] package#1 不存在")

    hash_rows = mysql_rows("SELECT account,CHAR_LENGTH(password_hash) FROM user ORDER BY id;", ARGS.mysql_db)
    runner.say("  口令哈希长度：" + json.dumps(hash_rows, ensure_ascii=False))
    for acc, ln in hash_rows:
        if int(ln) < 80:
            ok = False
            runner.say("  [FAIL] %s password_hash 长度异常（%s）" % (acc, ln))

    return ok, c, got_users, got_pkgs


def main():
    runner = Runner(ARGS.log)
    runner.say("== step7.5 测试数据重置 · %s ==" % time.strftime("%Y-%m-%d %H:%M:%S"))
    runner.say("目标：MySQL %s:%s/%s；Redis %s:%s；MQ booking.notify.queue + booking.notify.dlq"
               % (ARGS.mysql_host, ARGS.mysql_port, ARGS.mysql_db, ARGS.redis_host, ARGS.redis_port))

    runner.say("[1/6] 重置前盘点")
    before = counts(runner)
    runner.say("  before：" + json.dumps(before, ensure_ascii=False))

    if ARGS.redis_only:
        runner.say("[2/6] --redis-only：只清 Redis 本项目键，不动库/队列")
        redis_info = redis_clear(runner)
        after = counts(runner)
        runner.say("  库计数（应保持不变）：" + json.dumps(after, ensure_ascii=False))
        ok = (after.get("user") == EXPECT_USERS and after.get("package") == EXPECT_PACKAGES
              and after.get("booking") == EXPECT_BOOKINGS and after.get("notify_log") == EXPECT_NOTIFY_LOGS)
        runner.say("RESULT: " + ("PASS" if ok else "FAIL"))
        runner.finish()
        return 0 if ok else 1

    runner.say("[2/6] 备份")
    backup_path = backup(runner) if not ARGS.dry_run else None

    if ARGS.dry_run:
        runner.say("[3/6] --dry-run：跳过写库/清缓存/清队列")
        runner.finish()
        runner.say("DRY-RUN OK")
        return 0

    runner.say("[3/6] 重建数据库（TRUNCATE + init.sql 种子）")
    truncate_sql = (
        "SET FOREIGN_KEY_CHECKS=0;\n"
        "TRUNCATE TABLE booking;\n"
        "TRUNCATE TABLE notify_log;\n"
        "TRUNCATE TABLE user;\n"
        "TRUNCATE TABLE package;\n"
        "SET FOREIGN_KEY_CHECKS=1;\n"
    )
    mysql_run(truncate_sql, db=ARGS.mysql_db)
    runner.say("  TRUNCATE booking / notify_log / user / package 完成")
    if not os.path.isfile(ARGS.init_sql):
        runner.say("  [FAIL] 找不到 init.sql：%s" % ARGS.init_sql)
        runner.finish()
        return 1
    with open(ARGS.init_sql, "r", encoding="utf-8") as f:
        init_sql = f.read()
    mysql_run(init_sql)
    runner.say("  重跑 init.sql 完成（2 账号 + 4 套餐）")

    runner.say("[4/6] 清 Redis 本项目键")
    redis_info = redis_clear(runner)

    runner.say("[5/6] 清 MQ 遗留消息")
    mq_info = mq_purge(runner) if not ARGS.no_mq else {"purged": False, "reason": "no-mq"}

    runner.say("[6/6] 机器断言")
    ok, after, got_users, got_pkgs = assert_all(runner)

    summary = {
        "step": "7.5",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mysql": "%s:%s/%s" % (ARGS.mysql_host, ARGS.mysql_port, ARGS.mysql_db),
        "redis": "%s:%s" % (ARGS.redis_host, ARGS.redis_port),
        "before": before,
        "after": after,
        "backup": backup_path,
        "redis": redis_info,
        "mq": mq_info,
        "users": got_users,
        "packages": got_pkgs,
        "pass": bool(ok),
    }
    json_path = os.path.join(EVIDENCE_DIR, "step7_5_reset.json")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    runner.say("")
    if ok:
        runner.say("RESULT: PASS —— 库已恢复「2 账号 + 4 套餐」最小种子，可直接交接第 8 步")
        runner.say("证据：%s；%s" % (runner.log_path, json_path))
    else:
        runner.say("RESULT: FAIL —— 断言未全绿，不得交接第 8 步")
    runner.finish()
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="step7.5 测试数据重置（项目专用）")
    parser.add_argument("--mysql-host", default=os.environ.get("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--mysql-port", type=int, default=int(os.environ.get("MYSQL_PORT", "3307")))
    parser.add_argument("--mysql-user", default=os.environ.get("MYSQL_USER", "root"))
    parser.add_argument("--mysql-password", default=os.environ.get("MYSQL_PASSWORD", "123456"))
    parser.add_argument("--mysql-db", default=os.environ.get("MYSQL_DB", "uniapp_booking"))
    parser.add_argument("--redis-host", default=os.environ.get("REDIS_HOST", "127.0.0.1"))
    parser.add_argument("--redis-port", type=int, default=int(os.environ.get("REDIS_PORT", "6379")))
    parser.add_argument("--redis-password", default=os.environ.get("REDIS_PASSWORD") or None)
    parser.add_argument("--init-sql", default=os.environ.get("INIT_SQL", DEFAULT_INIT_SQL))
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--no-mq", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--redis-only", action="store_true", help="只清 Redis 本项目键（重置后回归完再清一次缓存/探针 nonce）")
    parser.add_argument("--log", default=None, help="日志路径，默认 07_联调/evidence/step7_5_reset.log")
    ARGS = parser.parse_args()
    sys.exit(main())
