#!/usr/bin/env python3
"""
公开推送前硬闸（prepush_check）——第 10.5 步 push 前最后一道机器检查。

背景：`git push` 之后密钥/大文件/运行数据一旦推到公开仓库就撤回不了。
本脚本在 push 之前的本地仓库上做四项硬检查：

  1. .gitignore 覆盖：必须包含 .env、node_modules、运行数据（runtime/data/*.db 等）
  2. git 历史密钥扫描：`git log -p --all` 全分支逐行扫疑似密钥
     （sk- / AKIA / ghp_ / xox / 私钥块 / Bearer / 带账号的数据库连接串 /
      password=、api_key= 一类赋值），跳过明显占位值
  3. 被跟踪的危险文件：`git ls-files` 里的 .env（不含 .env.example 等模板）、>5MB 大文件
  4. 远端可见性：`gh repo view --json visibility` 尽力检查。
     WORKFLOW_步骤定义.md step10.5 要求仓库必须 public（作品集展示），因此 private/internal → 红；
     public → 警告（提醒推送即公开且不可撤回、确认历史已清零）；
     查不到（未装 gh / 未登录 / 无远端）→ SKIP 不阻塞。

豁免：仓库根 `.secretignore`（与 security_scan_secrets.py 共用同一份清单）
     命中的「测试夹具/示例」文件在历史扫描中跳过并计入 ignored。

退出码：0 = 四项均无红项（可以有警告/跳过）；1 = 至少一项红，禁止 push。
使用方法：
    python scripts/prepush_check.py
    python scripts/prepush_check.py --json
"""

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

LARGE_FILE_BYTES = 5 * 1024 * 1024  # >5MB 视为不该进 Git 的大文件
MAX_FINDINGS_SHOWN = 20

# 历史扫描规则： (规则名, 正则, 取值分组索引)
# 分组索引 None 表示取整个匹配；否则取 group(n) 做占位符判断
HISTORY_SECRET_PATTERNS = [
    ("OpenAI Key", r"\bsk-[A-Za-z0-9]{20,}\b", None),
    ("AWS Access Key", r"\bAKIA[0-9A-Z]{16}\b", None),
    ("GitHub Token", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", None),
    ("GitHub PAT", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", None),
    ("Slack Token", r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b", None),
    ("Private Key Block", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", None),
    ("Bearer Token", r"\bBearer\s+[A-Za-z0-9_\-\.]{20,}", None),
    ("DB Conn With Password",
     r"\b(?:mysql|postgres(?:ql)?|mongodb(?:\+srv)?|redis)://[^:/\s@]+:[^@\s]+@", None),
    ("Password Assignment",
     r"(?i)\b[\w]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
     r"private[_-]?key|client[_-]?secret)[\w]*\b\s*[:=]\s*[\"']?([^\s\"',;]{6,})", 1),
]

# 明显占位值（小写子串匹配）——命中即跳过，不算泄露
PLACEHOLDER_TOKENS = {
    "example", "placeholder", "change-me", "changeme", "your-", "your_", "your",
    "xxx", "xxxx", "todo", "test", "demo", "sample", "fake", "dummy",
    "secret_here", "key_here", "placeholder", "redacted", "masked", "none",
    "null", "password", "passwd", "****", "ollama",
    "dev-local", "dev_local", "not-used", "not_used", "unused", "n-a", "n/a",
}

# proto / 基础类型名（#101）：口令/令牌字段后标注的类型名不是字面量密钥
TYPE_NAMES = {
    "string", "int32", "int64", "uint32", "uint64", "sint32", "sint64",
    "fixed32", "fixed64", "sfixed32", "sfixed64", "bool", "bytes", "float",
    "double", "map", "repeated", "message", "enum",
}

# 代码里读配置的写法（不是字面量密钥）：settings.API_KEY / os.getenv(...) / st.text_input( 等
CODE_REF_PREFIXES = (
    "settings.", "config.", "cfg.", "env.", "os.", "self.", "this.", "process.",
    "st.", "system.", "ctx.", "app.", "props.", "data.", "options.", "params.",
    "db.", "conn.", "client.", "conf.", "getenv.", "environ.",
)


# ---------- 基础工具 ----------

def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    """跑命令，返回 (returncode, stdout, stderr)。命令不存在返回 127。"""
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", f"命令不存在：{cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"命令超时（{timeout}s）：{' '.join(cmd)}"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _tail(text: str, lines: int = 3) -> str:
    rows = [r for r in (text or "").strip().splitlines() if r.strip()]
    return " / ".join(rows[-lines:])


def _normalize_rel(rel) -> str:
    text = str(rel).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def load_secretignore(root: Path) -> list[str]:
    """读根目录 .secretignore（相对根路径 / fnmatch glob，# 注释）。"""
    ignore_file = root / ".secretignore"
    if not ignore_file.exists():
        return []
    patterns = []
    for line in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            patterns.append(_normalize_rel(line))
    return patterns


def is_ignored(rel: str, patterns: list[str]) -> bool:
    rel = _normalize_rel(rel)
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def _looks_placeholder(value: str) -> bool:
    """明显占位/模板值（example、${VAR}、process.env、<...>、your-key 等）→ 跳过。"""
    low = (value or "").strip().strip("\"'`").lower()
    if not low:
        return True
    if low.startswith(("${", "{{", "<", "$", "%(", "env.", "os.getenv", "process.env")):
        return True
    return any(tok in low for tok in PLACEHOLDER_TOKENS)


def _looks_code_reference(value: str) -> bool:
    """值本身是读配置的代码表达式而非字面量（settings.API_KEY / st.text_input( / API_KEY）→ 跳过。"""
    low = (value or "").strip().strip("\"'`").lower()
    if not low:
        return True
    if any(low.startswith(prefix) for prefix in CODE_REF_PREFIXES):
        return True
    if any(ch in value for ch in "()[]{}"):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", value or ""):
        return True  # 全大写常量/环境变量名
    return False


def _looks_type_name(value: str) -> bool:
    """值是 proto/基础类型名（string/int32/bool…）或 old/new 这类局部变量名，不是字面量密钥（#101）。"""
    low = (value or "").strip().strip("\"'`").lower()
    if low in TYPE_NAMES:
        return True
    # 局部变量名：纯标识符（字母/数字/_/-），且是 old/new/prev/current 这类交接变量，长度 <6
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]{0,5}", value or "") and low in (
        "old", "new", "prev", "next", "cur", "tmp", "val", "item",
    ):
        return True
    return False


def _is_false_positive(value: str) -> bool:
    return _looks_placeholder(value) or _looks_code_reference(value) or _looks_type_name(value)


# ---------- 四项检查 ----------

def check_gitignore(root: Path) -> dict:
    """检查 .gitignore 是否覆盖 .env / node_modules / 运行数据。"""
    result = {"check": ".gitignore 覆盖（.env / node_modules / 运行数据）", "status": "ok",
              "details": "", "items": []}
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        result["status"] = "red"
        result["details"] = "仓库根缺 .gitignore"
        return result

    lines = []
    for raw in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)

    missing = []
    env_ok = any(
        line == ".env" or line.startswith(".env") or line in ("*.env", ".env*")
        for line in lines
    )
    if not env_ok:
        missing.append(".env")
    if not any("node_modules" in line for line in lines):
        missing.append("node_modules")
    data_markers = ("runtime", "*.db", "data/", "/data", "uploads", "sqlite", "logs/")
    if not any(marker in line for line in lines for marker in data_markers):
        missing.append("运行数据（runtime/ data/ *.db 一类）")

    if missing:
        result["status"] = "red"
        result["details"] = "缺少规则：" + "、".join(missing)
        result["items"] = missing
    else:
        result["details"] = f"{len(lines)} 条规则，必需三类均覆盖"
    return result


def _is_env_template(name: str) -> bool:
    """.env 模板文件按后缀模式识别（#100）：`.env.example*` / `.env.sample*` / `.env.*.template`，不枚举文件名。"""
    if not name.startswith(".env."):
        return False
    suffix = name[len(".env."):]
    return (suffix.startswith("example") or suffix.startswith("sample")
            or suffix.endswith(".template") or suffix.endswith(".tpl"))


def check_tracked_files(root: Path) -> dict:
    """检查被 Git 跟踪的 .env 与 >5MB 大文件。"""
    result = {"check": "被跟踪的危险文件（.env / >5MB）", "status": "ok",
              "details": "", "items": []}
    code, out, err = _run(["git", "ls-files", "-z"], root, timeout=120)
    if code != 0:
        result["status"] = "red"
        result["details"] = f"git ls-files 失败：{_tail(err)}"
        return result
    tracked = [f for f in out.split("\0") if f]

    env_tracked = []
    large_tracked = []
    for rel in tracked:
        name = Path(rel).name
        is_real_env = name == ".env" or (
            name.startswith(".env.") and not _is_env_template(name)
        )
        if is_real_env:
            env_tracked.append(rel)
        full = root / rel
        try:
            if full.is_file() and full.stat().st_size > LARGE_FILE_BYTES:
                large_tracked.append((rel, full.stat().st_size))
        except OSError:
            continue

    problems = []
    if env_tracked:
        problems.append(f"{len(env_tracked)} 个真实 .env 被 Git 跟踪")
        result["items"].extend(f"tracked .env: {p}" for p in env_tracked[:MAX_FINDINGS_SHOWN])
    if large_tracked:
        problems.append(f"{len(large_tracked)} 个 >5MB 大文件被 Git 跟踪")
        result["items"].extend(
            f"大文件: {p}（{size / 1024 / 1024:.1f}MB）" for p, size in large_tracked[:MAX_FINDINGS_SHOWN]
        )
    if problems:
        result["status"] = "red"
        result["details"] = "；".join(problems)
    else:
        result["details"] = f"跟踪 {len(tracked)} 个文件，无 .env、无 >5MB 大文件"
    return result


def check_history_secrets(root: Path, ignore_patterns: list[str]) -> dict:
    """`git log -p --all` 全历史扫描疑似密钥。"""
    result = {"check": "Git 历史密钥扫描（git log -p --all）", "status": "ok",
              "details": "", "items": [], "ignored": 0}
    code, out, err = _run(
        ["git", "-c", "core.quotepath=false", "log", "-p", "--all", "--no-color", "--no-ext-diff"],
        root, timeout=300)
    if code != 0:
        # 没有 commit 的空仓库不算红，但也判定不了
        result["status"] = "skip"
        result["details"] = f"无法读取 Git 历史：{_tail(err or out)}"
        return result

    ignored_hit_files = set()
    findings = []
    seen = set()
    sha = ""
    cur_file = ""
    for raw in out.splitlines():
        if raw.startswith("commit "):
            sha = raw[7:].strip()[:10]
            cur_file = ""
            continue
        if raw.startswith("+++ b/"):
            cur_file = _normalize_rel(raw[6:].strip().strip('"'))
            continue
        if raw.startswith("+++ "):
            # 新增文件 /dev/null 或 git 对特殊路径加引号的输出
            target = raw[4:].strip().strip('"')
            cur_file = _normalize_rel(target[2:]) if target.startswith("b/") else ""
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        added = raw[1:]
        if not added.strip():
            continue
        if cur_file and is_ignored(cur_file, ignore_patterns):
            ignored_hit_files.add(cur_file)
            continue
        for rule, pattern, group in HISTORY_SECRET_PATTERNS:
            m = re.search(pattern, added)
            if not m:
                continue
            value = m.group(group) if group is not None else m.group(0)
            if _is_false_positive(value):
                continue
            key = (rule, value[:60])
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "rule": rule,
                "file": cur_file or "(未知文件)",
                "commit": sha,
                "matched": m.group(0)[:100],
            })

    result["ignored"] = len(ignored_hit_files)
    if findings:
        result["status"] = "red"
        result["details"] = (f"历史中发现 {len(findings)} 处疑似密钥（去重后；"
                             f".secretignore 跳过 {len(ignored_hit_files)} 个测试夹具文件）")
        result["items"] = [
            f"[{f['rule']}] {f['file']} @ {f['commit']}：{f['matched']}"
            for f in findings[:MAX_FINDINGS_SHOWN]
        ]
        if len(findings) > MAX_FINDINGS_SHOWN:
            result["items"].append(f"…还有 {len(findings) - MAX_FINDINGS_SHOWN} 处未列出")
    else:
        result["details"] = ("历史中未发现疑似密钥"
                             + (f"（.secretignore 跳过 {len(ignored_hit_files)} 个测试夹具文件）"
                                if ignored_hit_files else ""))
    return result


def check_remote_visibility(root: Path) -> dict:
    """尽力用 gh 查远端可见性：WORKFLOW_步骤定义.md step10.5 要求仓库必须 public，private 判红。"""
    result = {"check": "仓库可见性（gh repo view --json visibility）", "status": "skip",
              "details": "", "items": []}
    gh = shutil.which("gh")
    if not gh:
        result["details"] = "未安装 gh CLI，跳过（无法查远端可见性）"
        return result
    code, out, err = _run([gh, "repo", "view", "--json", "visibility,nameWithOwner"],
                          root, timeout=30)
    if code != 0:
        result["details"] = f"gh 查询失败（未登录/无远端仓库？）：{_tail(err)}"
        return result
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        result["details"] = f"gh 输出不是 JSON：{_tail(out)}"
        return result
    visibility = (data.get("visibility") or "").upper()
    name = data.get("nameWithOwner") or ""
    if visibility == "PUBLIC":
        result["status"] = "warn"
        result["details"] = (f"远端仓库 {name} 是 PUBLIC（符合WORKFLOW_步骤定义.md step10.5「必须 public」）——"
                             f"推送即公开且不可撤回，请确认历史密钥/大文件两项已清零")
    elif visibility in ("PRIVATE", "INTERNAL"):
        result["status"] = "red"
        result["details"] = (f"远端仓库 {name} 是 {visibility} —— WORKFLOW_步骤定义.md step10.5 要求仓库必须 public"
                             f"（作品集展示用途），private 建仓违规；请先改 public 再 push")
    elif visibility:
        result["status"] = "warn"
        result["details"] = f"远端仓库 {name} 可见性 {visibility}（未识别的取值，人工确认）"
    else:
        result["details"] = "gh 未返回 visibility 字段"
    return result


# ---------- 入口 ----------

def main(root_dir: str, as_json: bool = False) -> int:
    start = Path(root_dir).resolve()
    code, out, err = _run(["git", "rev-parse", "--show-toplevel"], start, timeout=30)
    if code != 0 or not out.strip():
        print(f"❌ 不是 Git 仓库（或 git 不可用）：{start}")
        print(f"   {_tail(err or out)}")
        return 1
    root = Path(out.strip()).resolve()

    code, branch, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root, timeout=15)
    code2, remote, _ = _run(["git", "remote", "-v"], root, timeout=15)
    branch = branch.strip() if code == 0 else "(未知)"
    remote_url = ""
    for line in (remote or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "origin":
            remote_url = parts[1]
            break

    ignore_patterns = load_secretignore(root)
    results = [
        check_gitignore(root),
        check_history_secrets(root, ignore_patterns),
        check_tracked_files(root),
        check_remote_visibility(root),
    ]

    reds = [r for r in results if r["status"] == "red"]
    warns = [r for r in results if r["status"] == "warn"]
    skips = [r for r in results if r["status"] == "skip"]

    if as_json:
        print(json.dumps({
            "repo": str(root),
            "branch": branch,
            "remote": remote_url,
            "all_green": not reds,
            "checks": results,
        }, ensure_ascii=False, indent=2))
        return 0 if not reds else 1

    print("=" * 60)
    print("公开推送前硬闸（prepush_check）")
    print(f"仓库：{root}")
    print(f"分支：{branch}" + (f"    远端：{remote_url}" if remote_url else "    （无 origin 远端）"))
    print("=" * 60)
    icons = {"ok": "✅", "warn": "⚠️ ", "skip": "⏭️ ", "red": "❌"}
    for i, r in enumerate(results, 1):
        print(f"\n[{i}/{len(results)}] {icons.get(r['status'], '?')} {r['check']}")
        if r["details"]:
            print(f"     {r['details']}")
        for item in r.get("items", []):
            print(f"     - {item}")

    print("\n" + "=" * 60)
    if reds:
        print(f"🔴 未通过：{len(reds)} 项红——禁止 push，修完重跑本脚本。")
        print("   历史密钥处理：重置密钥 → 用 git filter-repo/BFG 清理历史 → 重新扫描确认。")
        return 1
    print("🟢 四项检查无红项，可以 push。"
          + (f"（{len(warns)} 项警告请人工确认）" if warns else "")
          + (f"（{len(skips)} 项跳过）" if skips else ""))
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
    ap = argparse.ArgumentParser(description="公开推送前硬闸：.gitignore / 历史密钥 / tracked 危险文件 / 远端可见性")
    ap.add_argument("root", nargs="?", default=".", help="仓库目录（默认当前目录）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()
    sys.exit(main(a.root, a.json))
