"""数据库访问层（L6 / T20 / D-50~D-52、D-56）。

双账号双池：api 只读走 ecom_ro（SELECT only），采集/清洗/报表走 ecom_rw；
DDL 与账号管理只用 root（由 cli initdb 持有），业务代码拿不到 DDL 权限（§5.3）。
不引入 ORM/DBUtils（架构 §1.2）：PyMySQL + 自管 FIFO 池即可，报表 SQL 要窗口函数，手写更可控。
"""
from __future__ import annotations

import re
import time
from contextlib import contextmanager
from pathlib import Path

import pymysql

from app.config import BACKEND_ROOT, ConfigError, settings

_SQL_DIR = BACKEND_ROOT / "sql"


class DbNotReady(Exception):
    """DB 不可达：API 层转 50301，任务层直接失败并告警（不静默重试到天亮，架构 §3 L9）。"""


class _Pool:
    """极简 FIFO 连接池：PyMySQL 无官方池，DBUtils 又不在依赖表（§1.2）。
    借出前 ping(reconnect=True) 复活长闲置连接；异常连接直接丢弃不回池。
    """

    def __init__(self, user: str, password: str, database: str, size: int):
        s = settings()
        self._cfg = dict(
            host=s.db_host, port=s.db_port, user=user, password=password,
            database=database, charset="utf8mb4", autocommit=False,
            cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
        )
        self._size = size
        self._free: list[pymysql.connections.Connection] = []
        self._created = 0

    @contextmanager
    def borrow(self):
        conn = None
        if self._free:
            conn = self._free.pop()
        elif self._created < self._size:
            conn = pymysql.connect(**self._cfg)
            self._created += 1
        if conn is None:
            # 池满：简单同步等待（本机单实例、并发低，避免引入队列复杂度）
            deadline = time.monotonic() + 5
            while not self._free and time.monotonic() < deadline:
                time.sleep(0.05)
            if not self._free:
                raise DbNotReady("连接池耗尽")
            conn = self._free.pop()
        try:
            conn.ping(reconnect=True)
            yield conn
            self._free.append(conn)
        except Exception:
            try:
                conn.close()
            finally:
                self._created -= 1  # 该连接不再回池，下次借用会重建
            raise


_pools: dict[str, _Pool] = {}


def _pool(kind: str) -> _Pool:
    if kind not in _pools:
        s = settings()
        if kind == "ro":
            _pools[kind] = _Pool(s.db_ro_user, s.db_ro_password, s.db_name, s.ro_pool_size)
        elif kind == "rw":
            _pools[kind] = _Pool(s.db_rw_user, s.db_rw_password, s.db_name, s.rw_pool_size)
        elif kind == "root":
            _pools[kind] = _Pool(s.db_root_user, s.db_root_password, s.db_name, 2)
        else:
            raise ValueError(kind)
    return _pools[kind]


# ---------------------------------------------------------------- 对外接口
def query(sql: str, params: dict | None = None, pool: str = "ro") -> list[dict]:
    """只读查询（默认 ro 账号）。列名保持 snake_case，JSON 列返回 str 由调用方解析。"""
    with _pool(pool).borrow() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            return list(cur.fetchall())


def execute(sql: str, params: dict | tuple | None = None, pool: str = "rw") -> int:
    """单条写（rw 账号）。params=None 时跳过 %-格式化（含 '%' 的 DDL/账号语句必需）。"""
    with _pool(pool).borrow() as conn:
        try:
            with conn.cursor() as cur:
                if params is None:
                    cur.execute(sql)
                else:
                    cur.execute(sql, params)
                conn.commit()
                return cur.lastrowid if cur.lastrowid else cur.rowcount
        except Exception:
            conn.rollback()
            raise


def execute_many(sql: str, seq: list[tuple], pool: str = "rw") -> int:
    """批量写（rw 账号）。PyMySQL executemany 自身无事务边界，这里 commit 一次。"""
    if not seq:
        return 0
    with _pool(pool).borrow() as conn:
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, seq)
                conn.commit()
            return len(seq)
        except Exception:
            conn.rollback()
            raise


@contextmanager
def transaction(pool: str = "rw"):
    """页级事务入口：stg + task_run_item + cursor 三件事同事务提交（D-23）。"""
    with _pool(pool).borrow() as conn:
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def wait_db(timeout: int = 60, pool: str = "rw") -> None:
    """等 DB 就绪（P1-08）：1s 退避，超时抛 DbNotReady，由 CLI/调度层决定失败与告警。"""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with _pool(pool).borrow() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return
        except Exception as e:
            if time.monotonic() >= deadline:
                raise DbNotReady(f"MySQL 在 {timeout}s 内不可达: {e}")
            time.sleep(1)


# ---------------------------------------------------------------- SQL 文件装载
def read_sql(name: str) -> str:
    """读 sql/queries/<name>.sql 单查询文件（ADR-08：报表与看板共用同一组 SQL）。"""
    path = _SQL_DIR / "queries" / f"{name}.sql"
    if not path.exists():
        raise ConfigError(f"缺少查询文件 {path}")
    return strip_sql_comments(path.read_text(encoding="utf-8"))


def read_sql_named(name: str) -> dict[str, str]:
    """读含 `-- name: xxx` 分段的查询文件 → {段名: SQL}（多口径共存一个文件）。"""
    text = read_sql(name)
    out: dict[str, str] = {}
    cur_name, buf = "default", []
    for line in text.splitlines():
        m = re.match(r"--\s*name:\s*(\S+)", line.strip())
        if m:
            if any(l.strip() for l in buf):
                out[cur_name] = "\n".join(buf).strip()
            cur_name, buf = m.group(1), []
        else:
            buf.append(line)
    if any(l.strip() for l in buf):
        out[cur_name] = "\n".join(buf).strip()
    return out


def strip_sql_comments(sql: str) -> str:
    lines = [l for l in sql.splitlines() if not l.strip().startswith("--")]
    return "\n".join(lines).strip()


def split_statements(sql_text: str) -> list[str]:
    """把 DDL 文件按行尾分号切分（DDL 内无字符串分号，安全）。"""
    stmts, buf = [], []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.upper() == "USE ecom_scrape;":
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";")
            if stmt:
                stmts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip().rstrip(";")
    if tail:
        stmts.append(tail)
    return stmts


# ---------------------------------------------------------------- 账号与分区
def create_accounts() -> list[str]:
    """initdb 专用（root 会话）：最小权限双账号（§5.3）。幂等：已存在则改口令对齐 .env。"""
    s = settings()
    stmts = [
        f"CREATE USER IF NOT EXISTS '{s.db_ro_user}'@'%' IDENTIFIED BY '{_esc(s.db_ro_password)}'",
        f"CREATE USER IF NOT EXISTS '{s.db_rw_user}'@'%' IDENTIFIED BY '{_esc(s.db_rw_password)}'",
        f"ALTER USER '{s.db_ro_user}'@'%' IDENTIFIED BY '{_esc(s.db_ro_password)}'",
        f"ALTER USER '{s.db_rw_user}'@'%' IDENTIFIED BY '{_esc(s.db_rw_password)}'",
        # ro：只读。rw：业务表 DML；DELETE 仅为 prune/清理保留（§7.4），DDL 只归 root
        f"GRANT SELECT ON {s.db_name}.* TO '{s.db_ro_user}'@'%'",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {s.db_name}.* TO '{s.db_rw_user}'@'%'",
        "FLUSH PRIVILEGES",
    ]
    return stmts


def _esc(v: str) -> str:
    return v.replace("'", "''")


def ensure_partitions() -> list[str]:
    """跨月分区自动补齐（D-51）：保证当前月与未来 2 个月都有分区，幂等。

    实现：REORGANIZE pmax 逐月拆分——pmax 必须始终保留为兜底（MAXVALUE）。
    返回执行过的 ALTER 语句（无操作返回空列表，调用方可用于留证）。
    """
    from datetime import date as _date

    def _month_end(d: _date, ahead: int) -> str:
        y, m = d.year, d.month + ahead
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        return f"{y + (1 if m == 12 else 0):04d}-{(1 if m == 12 else m + 1):02d}-01"

    today = _date.today()
    needed_until = _month_end(today, 3)  # 覆盖当月 +2 月的写入（含月末跨月余量）

    rows = query(
        "SELECT PARTITION_NAME, PARTITION_DESCRIPTION FROM information_schema.PARTITIONS "
        "WHERE TABLE_SCHEMA=%(schema)s AND TABLE_NAME='price_snapshot' AND PARTITION_NAME IS NOT NULL",
        {"schema": settings().db_name},
        pool="root",
    )
    if not rows:
        return []
    bounds = [
        r["PARTITION_DESCRIPTION"].strip("'")
        for r in rows
        if r["PARTITION_NAME"] != "pmax"
    ]
    alters: list[str] = []
    latest = max(bounds) if bounds else "1970-01-01"
    while latest < needed_until:
        # latest 是某月 1 号：下一个月度分区覆盖该月，边界为再下月 1 号
        y, m = map(int, latest.split("-")[:2])
        m += 1
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        next_bound = f"{y:04d}-{m:02d}-01"
        pname = f"p{y}{m:02d}"
        alter = (
            f"ALTER TABLE price_snapshot REORGANIZE PARTITION pmax INTO "
            f"(PARTITION {pname} VALUES LESS THAN ('{next_bound}'), "
            f"PARTITION pmax VALUES LESS THAN (MAXVALUE))"
        )
        execute(alter, pool="root")
        alters.append(alter)
        latest = next_bound
    return alters
