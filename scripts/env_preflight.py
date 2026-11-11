#!/usr/bin/env python3
"""
本地环境就绪预检（step03 架构评审人工复核时跑）
检查本机装了哪些工具、版本是否达标、常用端口是否被占、内存余量够不够。
专治「架构文档写得很漂亮，结果本机没装 Java / 端口被占了」。

使用方法：
    python scripts/env_preflight.py
    python scripts/env_preflight.py --ports 8080,3306,6379,9092
    python scripts/env_preflight.py --project saas-workflow-agent   # 从端口分配表自动读端口
    python scripts/env_preflight.py --verify-config projects/<项目名>   # 配置值实测
    python scripts/env_preflight.py --env-coverage                     # 裸跑 = 扫描当前目录
    python scripts/env_preflight.py --env-coverage projects/<项目名>    # 代码环境变量引用 vs .env.example 差集
    python scripts/env_preflight.py --smoke                            # 裸跑 = 默认 URL（见 DEFAULT_SMOKE_URL）
    python scripts/env_preflight.py --smoke http://127.0.0.1:8081/health,http://127.0.0.1:5173/  # HTTP 冒烟断言

退出码：0 = 工具齐全/版本达标/端口空闲/配置与冒烟通过；
        1 = 必需工具缺失或版本不达标 / 端口被占 / 配置实测失败 / 冒烟失败。
        内存不足保留为警告（不阻塞），但仍会打印在警告清单里。

--smoke 说明（改进建议 #51）：对已启动的服务发真实 HTTP GET，断言返回码；用于 5A/5B 完成定义与第 6 步阶段一，
    防止「进程活着但接口 500 / 页面白屏」被算作启动成功。

--verify-config 说明：静态检查查不出「配置写了但连不上」。
    ① 读取项目内 .env / .env.example，解析 MYSQL/REDIS/RABBITMQ/QDRANT/MQTT 的 host:port
    ② 逐项 TCP 探活；Redis 发 PING（有密码先 AUTH）；MySQL 有 mysql 客户端时执行 SELECT 1
    ③ 比对多个 .env 中同名令牌（*TOKEN/*SECRET/*KEY）的值，不一致直接报错
    ④ .env.example 里非空、非「请填写」的键在 .env 中缺失 → 报错
"""

import argparse
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# 期望版本（下限，低于此判失败，退出码 1）
EXPECTED = {
    "java": (17, 0),
    "maven": (3, 8),
    "node": (18, 0),
    "npm": (9, 0),
    "docker": (20, 10),
    "docker compose": (2, 20),
    "python": (3, 9),
}

DEFAULT_PORTS = [8080, 3306, 5432, 6379, 9092, 8848, 9000, 9001, 8500]

# --smoke 裸跑时的默认冒烟 URL（文档可直接 `--smoke`，不再 argparse 报错）
DEFAULT_SMOKE_URL = "http://127.0.0.1:8080/health"


def run(cmd: list[str]) -> str | None:
    """跑命令，返回 stdout+stderr 合并字符串；找不到命令返回 None。
    Windows 上统一走 shell=True，避免 .cmd/.ps1/.bat 路径解析问题。"""
    exe = cmd[0]
    # 先确认命令在 PATH 里
    if shutil.which(exe) is None:
        found = None
        for ext in (".cmd", ".bat", ".exe", ".ps1", ""):
            p = shutil.which(exe + ext)
            if p:
                found = p
                break
        if not found:
            return None
    try:
        shell_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        r = subprocess.run(
            shell_cmd, capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="ignore", shell=True,
        )
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def parse_ver(text: str) -> tuple[int, int] | None:
    """从命令输出里抠主.次版本号。"""
    import re
    if not text:
        return None
    m = re.search(r"(\d+)\.(\d+)(?:\.\d+)?", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def check_tool(name: str, cmd: list[str]) -> tuple[str, str]:
    """返回 (状态, 描述)。状态: ok / low（版本不达标）/ warn（装了但版本号解析不出）/ missing。"""
    text = run(cmd)
    if text is None:
        return "missing", f"{name}: 未安装（{cmd[0]} 不在 PATH）"
    ver = parse_ver(text)
    if ver is None:
        return "warn", f"{name}: 已安装但无法解析版本号，输出首行: {text.strip().splitlines()[0] if text.strip() else '(空)'}"
    exp = EXPECTED.get(name)
    if exp and ver < exp:
        return "low", f"{name}: 检测到 {ver[0]}.{ver[1]}，期望 ≥ {exp[0]}.{exp[1]}（版本不达标）"
    return "ok", f"{name}: {ver[0]}.{ver[1]}"


def check_port(port: int) -> tuple[str, str]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        r = s.connect_ex(("127.0.0.1", port))
        if r == 0:
            return "busy", f"端口 {port}: 被占用（可能已有服务在跑，注意冲突）"
        return "free", f"端口 {port}: 空闲"
    finally:
        s.close()


SKIP_DIRS = {"node_modules", ".venv", "venv", "target", ".git", "__pycache__", "dist"}
PLACEHOLDERS = ("请填写", "changeme", "change-me", "your-", "xxx", "todo", "placeholder")

HOST_PORT_PREFIXES = {
    "MYSQL": 3306,
    "DB": 3306,
    "REDIS": 6379,
    "RABBITMQ": 5672,
    "QDRANT": 6333,
}


def find_root(start: Path | None = None) -> Path:
    """向上找 WORKFLOW_工作流主控.md 所在目录作为仓库根。"""
    cur = (start or Path.cwd()).resolve()
    for _ in range(15):
        if (cur / "WORKFLOW_工作流主控.md").exists():
            return cur
        if cur == cur.parent:
            break
        cur = cur.parent
    return Path.cwd()


def parse_port_table(project_name: str) -> tuple[list[int], bool]:
    """解析 WORKFLOW_端口分配表.md，返回 (基础设施端口 + 该项目的后端/前端端口, 是否找到项目行)。
    找不到表或项目行时 found=False（调用方必须报错，禁止静默回退，改进建议 #68）。"""
    root = find_root()
    table = root / "WORKFLOW_端口分配表.md"
    if not table.exists():
        return [], False
    text = table.read_text(encoding="utf-8", errors="ignore")
    ports: set[int] = set()
    found = False
    infra_markers = ("MySQL", "Redis", "Kafka", "ClickHouse", "RabbitMQ", "Qdrant")
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("*") for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        # 基础设施表：第 1 列是服务名（如 "Redis 7.2"、"MySQL 8.0"）
        if any(cells[0].startswith(m) for m in infra_markers):
            m = re.search(r"\d+", cells[1])
            if m:
                ports.add(int(m.group()))
        # 后端/前端端口池：第 1 列是项目名（一格多端口全取，如 "8080(gw) / 8081 / 8082"）
        elif cells[0] == project_name:
            found = True
            for m in re.finditer(r"\d+", cells[1]):
                ports.add(int(m.group()))
    return sorted(ports), found


# 代码环境变量引用扫描（--env-coverage，改进建议 #69）
ENV_REF_PATTERNS = [
    # Python
    (re.compile(r'os\.getenv\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'), "py"),
    (re.compile(r'os\.environ(?:\.get)?\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'), "py"),
    (re.compile(r'os\.environ\[\s*["\']([A-Z_][A-Z0-9_]*)["\']'), "py"),
    # Java
    (re.compile(r'System\.getenv\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'), "java"),
    (re.compile(r'@Value\(\s*"\$\{([A-Z_][A-Z0-9_]*)'), "java"),
    # Node / TS
    (re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)'), "js"),
    (re.compile(r'process\.env\[\s*["\']([A-Z_][A-Z0-9_]*)["\']'), "js"),
]
CODE_SUFFIXES = {".py", ".java", ".js", ".ts", ".tsx", ".jsx"}


def scan_env_references(project_dir: Path) -> set[str]:
    """扫描项目代码中的环境变量引用，返回变量名集合。"""
    refs: set[str] = set()
    for p in project_dir.rglob("*"):
        if not p.is_file() or p.suffix not in CODE_SUFFIXES:
            continue
        rel = p.relative_to(project_dir)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat, _ in ENV_REF_PATTERNS:
            for m in pat.finditer(text):
                refs.add(m.group(1))
    return refs


def find_env_files(project_dir: Path, max_depth: int = 4) -> list[Path]:
    """找项目内的 .env / .env.example 等文件（跳过构建产物目录）"""
    out = []
    for p in project_dir.rglob(".env*"):
        try:
            rel = p.relative_to(project_dir)
        except ValueError:
            continue
        if not p.is_file() or len(rel.parts) - 1 > max_depth:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        out.append(p)
    # 真实 .env 优先于 .example，避免用模板占位值探测
    return sorted(out, key=lambda x: (".example" in x.name, str(x)))


def parse_env(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def is_placeholder(value: str) -> bool:
    low = (value or "").strip().lower()
    return (not low) or any(tok in low for tok in PLACEHOLDERS)


def targets_from_env(env: dict) -> list[dict]:
    """从一份 env 里推导需要探活的 host:port"""
    targets = []
    for prefix, default_port in HOST_PORT_PREFIXES.items():
        host = env.get(f"{prefix}_HOST")
        if not host or is_placeholder(host):
            continue
        raw_port = env.get(f"{prefix}_PORT") or default_port
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            port = default_port
        targets.append({"name": prefix, "host": host, "port": port, "env": env})
    # URL 形式：tcp://host:port、amqp://host:port、redis://host:port、jdbc:mysql://host:port
    for k, v in env.items():
        m = re.search(r"(?:tcp|amqp|redis|mysql)://(?:[^@/\s]+@)?([^:/?\s]+):(\d+)", v)
        if m and not is_placeholder(m.group(1)):
            targets.append({"name": k, "host": m.group(1), "port": int(m.group(2)), "env": env})
    return targets


def probe_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def probe_redis(host: str, port: int, password: str) -> tuple[bool, str]:
    s = None
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.settimeout(2)
        if password and not is_placeholder(password):
            s.sendall(f"AUTH {password}\r\n".encode())
            resp = s.recv(256)
            if not resp.startswith(b"+OK"):
                return False, f"AUTH 失败: {resp[:60]!r}"
        s.sendall(b"PING\r\n")
        resp = s.recv(256)
        if resp.strip() != b"+PONG":
            return False, f"PING 异常: {resp[:60]!r}"
        return True, "PING → +PONG"
    except Exception as e:
        return False, f"连接异常: {e}"
    finally:
        if s:
            s.close()


def probe_mysql(host: str, port: int, user: str, password: str) -> tuple[bool | None, str]:
    mysql = shutil.which("mysql")
    if not mysql:
        return None, "无 mysql 客户端，跳过登录验证（TCP 已通）"
    cmd = [mysql, f"-h{host}", f"-P{port}", f"-u{user or 'root'}", "-e", "SELECT 1",
           "--connect-timeout=3"]
    import os
    env = dict(os.environ)
    if password and not is_placeholder(password):
        env["MYSQL_PWD"] = password  # 不把密码放到命令行，避免进程列表泄露
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="ignore", env=env)
    except Exception as e:
        return False, f"mysql 执行异常: {e}"
    if r.returncode == 0:
        return True, "SELECT 1 OK"
    return False, (r.stderr or r.stdout).strip().splitlines()[-1][:200] if (r.stderr or r.stdout).strip() else "登录失败"


def check_token_drift(env_files: list[tuple[str, dict]]) -> list[str]:
    """不同 .env 中同名令牌值不一致 → 配置漂移（本项目真实踩坑：内部令牌 401）"""
    problems = []
    for i in range(len(env_files)):
        for j in range(i + 1, len(env_files)):
            a_name, a = env_files[i]
            b_name, b = env_files[j]
            for key in set(a) & set(b):
                if not re.search(r"(TOKEN|SECRET|KEY)$", key, re.IGNORECASE):
                    continue
                if is_placeholder(a[key]) or is_placeholder(b[key]):
                    continue
                if a[key] != b[key]:
                    problems.append(
                        f"配置漂移: {key} 在 {a_name} 与 {b_name} 不一致（双侧必须相同，否则恒 401）")
    return problems


def check_required_keys(project_dir: Path, env_files: list[Path]) -> list[str]:
    """模板里有非空值的必填键，.env 必须有且不能是占位值"""
    problems = []
    for example in env_files:
        if not any(tag in example.name for tag in (".example", ".sample", ".template")):
            continue
        real = example.with_name(".env")
        if not real.exists():
            problems.append(f"{example.relative_to(project_dir)} 存在但没有对应的 .env（未完成配置）")
            continue
        ex = parse_env(example)
        rv = parse_env(real)
        for key, value in ex.items():
            if is_placeholder(value):
                continue
            if key not in rv:
                problems.append(f"{real.relative_to(project_dir)} 缺少必填项 {key}")
            elif is_placeholder(rv[key]):
                problems.append(f"{real.relative_to(project_dir)} 的 {key} 仍是占位值「{rv[key]}」")
    return problems


def verify_config(project_dir: str) -> tuple[list[str], list[str]]:
    """配置值实测，返回 (problems, warns)"""
    root = Path(project_dir).resolve()
    print("\n--- 配置值实测（--verify-config）---")
    if not root.exists():
        return [f"项目目录不存在: {root}"], []

    env_files = find_env_files(root)
    if not env_files:
        print("  ⚠️  未找到 .env / .env.example，跳过配置实测")
        return [], []

    print(f"  发现 {len(env_files)} 个环境文件: "
          + ", ".join(str(p.relative_to(root)) for p in env_files))

    problems: list[str] = []
    warns: list[str] = []
    parsed = [(str(p.relative_to(root)), parse_env(p)) for p in env_files]

    # 目标去重：同一 host:port 只探一次
    targets: dict[tuple[str, int], dict] = {}
    for name, env in parsed:
        for t in targets_from_env(env):
            key = (t["host"], t["port"])
            if key not in targets:
                t["file"] = name
                targets[key] = t

    if not targets:
        print("  ⚠️  未从配置中解析到 host:port（检查 MYSQL_HOST/REDIS_HOST 等键）")

    for (host, port), t in targets.items():
        label = f"[{t['file']}] {t['name']} {host}:{port}"
        if not probe_tcp(host, port):
            problems.append(f"{label} TCP 不通（服务没起或端口写错）")
            print(f"  ❌ {label} TCP 不通")
            continue
        print(f"  ✅ {label} TCP 通")

        env = t["env"]
        upper = t["name"].upper()
        if upper.startswith("REDIS") or port == 6379:
            ok, msg = probe_redis(host, port, env.get("REDIS_PASSWORD", ""))
            print(f"     {'✅' if ok else '❌'} Redis 登录: {msg}")
            if ok:
                continue
            # 密码错与连接异常区分：密码错是硬错误
            if "AUTH" in msg:
                problems.append(f"{label} Redis 认证失败: {msg}")
            else:
                warns.append(f"{label} Redis 探活异常: {msg}")
        elif upper.startswith(("MYSQL", "DB")) or port in (3306, 3310):
            ok, msg = probe_mysql(host, port, env.get("MYSQL_USER", env.get("DB_USER", "")),
                                  env.get("MYSQL_PASSWORD", env.get("DB_PASSWORD", "")))
            if ok is None:
                print(f"     ⚠️  {msg}")
                warns.append(f"{label} {msg}")
            else:
                print(f"     {'✅' if ok else '❌'} MySQL 登录: {msg}")
                if not ok:
                    problems.append(f"{label} MySQL 登录失败: {msg}")

    # 令牌漂移 + 必填项
    drift = check_token_drift(parsed)
    for d in drift:
        print(f"  ❌ {d}")
    problems.extend(drift)

    required = check_required_keys(root, env_files)
    for r in required:
        print(f"  ❌ {r}")
    problems.extend(required)

    return problems, warns


def smoke_http(urls: list[str], expect: int) -> list[str]:
    """HTTP 冒烟断言：逐个 GET，返回码必须等于 expect；返回问题清单。"""
    import urllib.error
    import urllib.request

    print("\n--- HTTP 冒烟断言（--smoke）---")
    problems = []
    for url in urls:
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "workflow-smoke"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                status = resp.getcode()
                snippet = resp.read(200).decode("utf-8", errors="ignore").replace("\n", " ")[:80]
        except urllib.error.HTTPError as e:
            status = e.code
            snippet = (e.read(200) or b"").decode("utf-8", errors="ignore").replace("\n", " ")[:80]
        except Exception as e:
            problems.append(f"{url} 请求失败: {e}")
            print(f"  ❌ {url} 请求失败: {e}")
            continue
        if status == expect:
            print(f"  ✅ {url} → HTTP {status}  {snippet}")
        else:
            msg = f"{url} 返回 {status}，期望 {expect}"
            problems.append(msg)
            print(f"  ❌ {msg}  {snippet}")
    return problems


def check_memory() -> tuple[str, str]:
    """Windows 下用 ctypes 查物理内存；其他平台 best-effort。"""
    try:
        if sys.platform == "win32":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            avail_gb = stat.ullAvailPhys / (1024 ** 3)
            total_gb = stat.ullTotalPhys / (1024 ** 3)
            if avail_gb < 4:
                return "warn", f"内存: 总 {total_gb:.1f}GB，可用仅 {avail_gb:.1f}GB（Docker Compose 起多服务可能吃紧）"
            return "ok", f"内存: 总 {total_gb:.1f}GB，可用 {avail_gb:.1f}GB"
        else:
            return "unknown", "内存检查仅在 Windows 实现，请手动确认 16GB 内存在 Docker Desktop 启动后还剩多少"
    except Exception as e:
        return "unknown", f"内存检查失败: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default=",".join(map(str, DEFAULT_PORTS)),
                    help="要检查的端口列表，逗号分隔（--project 未指定时用此默认）")
    ap.add_argument("--project", default="",
                    help="项目名：自动从 WORKFLOW_端口分配表.md 读取该项目的基础设施+后端+前端端口")
    ap.add_argument("--verify-config", metavar="项目目录",
                    help="实测项目 .env 配置：TCP 探活 + Redis/MySQL 登录 + 双侧令牌比对 + 必填项")
    ap.add_argument("--env-coverage", nargs="?", const=".", default=None, metavar="项目目录",
                    help="配置完整性：扫描代码环境变量引用 vs .env.example 差集，缺 key 报红"
                         "（裸跑 --env-coverage 等价于当前目录 .）")
    ap.add_argument("--smoke", nargs="?", const=DEFAULT_SMOKE_URL, default=None, metavar="URLS",
                    help=f"HTTP 冒烟：逗号分隔的 URL 列表，逐个 GET 并断言返回码（用于 5A/5B/第6步）；"
                         f"裸跑 --smoke 默认检查 {DEFAULT_SMOKE_URL}")
    ap.add_argument("--smoke-expect", type=int, default=200,
                    help="--smoke 期望的 HTTP 状态码，默认 200")
    args = ap.parse_args()

    print("=" * 50)
    print("环境就绪预检（step03 架构评审辅助）")
    print("=" * 50)

    problems = []
    warns = []

    tools = [
        ("java", ["java", "-version"]),
        ("maven", ["mvn", "-v"]),
        ("node", ["node", "-v"]),
        ("npm", ["npm", "-v"]),
        ("docker", ["docker", "--version"]),
        ("docker compose", ["docker", "compose", "version"]),
        ("python", ["python", "--version"]),
    ]

    print("\n--- 工具版本 ---")
    for name, cmd in tools:
        st, desc = check_tool(name, cmd)
        icon = {"ok": "✅", "low": "❌", "warn": "⚠️ ", "missing": "❌"}[st]
        print(f"  {icon} {desc}")
        if st in ("missing", "low"):
            problems.append(desc)
        elif st == "warn":
            warns.append(desc)

    print("\n--- 端口占用 ---")
    if args.project:
        table_ports, found = parse_port_table(args.project)
        if not found:
            print(f"  ❌ WORKFLOW_端口分配表.md 中未找到项目「{args.project}」的端口行，无法自动解析。")
            print(f"     请先在端口分配表登记该项目端口，或改用 --ports 手动指定（不允许静默回退默认端口）。")
            return 1
        print(f"  ℹ️  从端口分配表读取 {args.project} 端口：{table_ports}")
        ports = table_ports
    else:
        ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    for p in ports:
        st, desc = check_port(p)
        icon = "✅" if st == "free" else "❌"
        print(f"  {icon} {desc}")
        if st == "busy":
            # 端口被占是硬失败（2026-11-08 起）：服务起不来时「环境就绪」是假绿
            problems.append(desc)

    print("\n--- 内存 ---")
    st, desc = check_memory()
    icon = {"ok": "✅", "warn": "⚠️ ", "unknown": "ℹ️ "}.get(st, "?")
    print(f"  {icon} {desc}")
    if st == "warn":
        warns.append(desc)

    if args.verify_config:
        cfg_problems, cfg_warns = verify_config(args.verify_config)
        problems.extend(cfg_problems)
        warns.extend(cfg_warns)

    if args.env_coverage:
        proj = Path(args.env_coverage).resolve()
        refs = scan_env_references(proj)
        # 找 .env.example
        env_example = None
        for p in find_env_files(proj):
            if p.name.endswith(".example") or p.name == ".env.example":
                env_example = p
                break
        print(f"\n--- 配置完整性（代码引用 vs .env.example）---")
        print(f"  扫描到代码环境变量引用 {len(refs)} 个")
        if env_example:
            example_keys = set(parse_env(env_example).keys())
            missing = refs - example_keys
            if missing:
                print(f"  ❌ 代码引用但 .env.example 缺失的 key（{len(missing)} 个）：")
                for k in sorted(missing):
                    print(f"     - {k}")
                problems.append(f".env.example 缺 {len(missing)} 个 key：{', '.join(sorted(missing)[:10])}")
            else:
                print(f"  ✅ 所有代码引用的环境变量在 .env.example 中均有定义")
            extra = example_keys - refs
            if extra:
                print(f"  ℹ️  .env.example 有但代码未引用（{len(extra)} 个，可能是配置项/默认值）：")
                for k in sorted(extra)[:20]:
                    print(f"     - {k}")
        else:
            print(f"  ⚠️  未找到 .env.example，跳过差集比对")
            warns.append(f"{proj.name} 缺少 .env.example，无法做配置完整性差集")

    if args.smoke:
        smoke_problems = smoke_http(
            [u.strip() for u in args.smoke.split(",") if u.strip()], args.smoke_expect)
        problems.extend(smoke_problems)

    print("\n" + "=" * 50)
    print(f"缺失 {len(problems)} 项，警告 {len(warns)} 项")
    if problems:
        print("\n❌ 必须处理（架构里依赖这些工具才能落地）：")
        for p in problems:
            print(f"  - {p}")
        print("\n处理方式：工具缺失/版本不达标 → 装/升级工具，或回 step02 换技术栈；"
              "端口被占 → 停掉占用进程或换端口；配置/冒烟失败 → 按条目修 .env/端口/令牌后重跑。")
        return 1
    if warns:
        print("\n⚠️  警告（不阻塞但评审时人工确认）：")
        for w in warns:
            print(f"  - {w}")
    print("\n✅ 环境就绪，可以进入架构评审人工复核。")
    return 0


def _force_utf8_output():
    """Windows 默认 cp936/GBK 控制台下打印中文/emoji 会 UnicodeEncodeError；入口处统一切 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    _force_utf8_output()
    sys.exit(main())
