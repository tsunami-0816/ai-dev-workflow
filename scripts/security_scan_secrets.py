#!/usr/bin/env python3
"""
安全扫描：硬编码密钥、密码、Token、数据库连接字符串检测
使用方法：
    python scripts/security_scan_secrets.py <项目根目录>            # 仅密钥扫描
    python scripts/security_scan_secrets.py <项目根目录> --sast     # 追加代码级 SAST 规则（第 8.5 步推荐）

--sast 规则（针对本项目真实踩过的坑，共 3 类）：
    ① 全局 AviatorEvaluator.execute(...)  —— 表达式必须走禁特性沙箱实例
    ② SQL 字符串拼接 / f-string 拼 SQL     —— 必须用参数化查询
    ③ Runtime.exec / os.system / shell=True —— 命令执行需白名单校验

.secretignore（仅限测试夹具/示例，防 CI 干净检出误报）：
    在扫描根目录放 `.secretignore`，每行一个「相对根目录」的精确路径或 fnmatch glob，
    `#` 开头或行尾 `#` 后为注释。命中文件打印 `⏭️ 忽略（.secretignore）: path` 并计入
    总结的 ignored 计数。口径：只放测试账号/示例占位，真实密钥一律修代码 + 重置，不许靠它绕。
"""

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

# 常见密钥模式（正则）
PATTERNS = [
    (r'["\']?(?:api[_-]?key|apikey|api[_-]?secret|secret[_-]?key|access[_-]?key)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']', 'API Key/Secret'),
    (r'["\']?(?:password|passwd|pwd|db[_-]?pass|database[_-]?password)["\']?\s*[:=]\s*["\']([^"\']{4,})["\']', 'Password'),
    (r'["\']?(?:token|auth[_-]?token|access[_-]?token|refresh[_-]?token)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-\.]{16,})["\']', 'Token'),
    (r'["\']?(?:private[_-]?key|rsa[_-]?private|ssh[_-]?key)["\']?\s*[:=]\s*["\']([^"\']{20,})["\']', 'Private Key'),
    (r'(?:mysql|postgres|mongodb|redis)://[^:]+:[^@]+@', 'Database Connection String'),
    (r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer Token'),
    (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API Key'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Token'),
    (r'xox[baprs]-[a-zA-Z0-9\-]{10,}', 'Slack Token'),
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', 'Private Key Block'),
]

# 排除目录
EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next', 'data', 'uploads', 'chroma'}

# 排除文件后缀
EXCLUDE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.zip', '.tar', '.gz', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.db', '.sqlite', '.pyc', '.so', '.dll', '.exe'}

# 常见占位符白名单（小写匹配）
PLACEHOLDERS = {'example', 'placeholder', 'change-me', 'changeme', 'your-', 'your_', 'xxx', 'xxxx', '...', 'todo', 'test', 'demo', 'sample', 'fake', 'dummy', 'secret_here', 'key_here'}

# 测试目录段（只认目录段，不再用路径任意子串判断——改进建议 #54：
# reset_test_data.py 曾因文件名含 test 被整类豁免，真实密码漏报）
TEST_DIR_SEGMENTS = {
    'test', 'tests', '__tests__', 'testcases', 'testcase',
    'e2e', 'spec', 'specs', 'fixtures', 'evidence',
    # 工作流产物目录：冒烟/联调/测试/安全/验收/体检里的脚本与夹具是测试上下文，
    # 命中降级为警告（仍需人工确认），不阻塞；生产代码在 05_代码/。
    '06_冒烟', '07_联调', '08_测试', '08.5_安全扫描', '09_验收', 'f2_体检',
}

def is_placeholder(text: str) -> bool:
    """判断是否为占位符而非真实密钥"""
    low = text.lower()
    return any(ph in low for ph in PLACEHOLDERS)

def is_test_context(filepath: Path, root: Path) -> bool:
    """判断是否为测试上下文（仅看目录段）：命中也只是降级为警告，不再整类跳过。"""
    try:
        parts = [p.lower() for p in filepath.relative_to(root).parts[:-1]]
    except ValueError:
        parts = [p.lower() for p in filepath.parts[:-1]]
    return any(p in TEST_DIR_SEGMENTS for p in parts)


# .secretignore：测试夹具/示例的精确豁免清单（相对扫描根目录，支持 fnmatch glob）
SECRETIGNORE_FILE = ".secretignore"


def _normalize_rel(rel) -> str:
    """统一成 POSIX 风格相对路径（Windows 反斜杠 → /）。"""
    text = str(rel).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def load_secretignore(root: Path) -> list[str]:
    """读根目录 .secretignore，返回归一化后的 pattern 列表；文件不存在返回空。"""
    ignore_file = root / SECRETIGNORE_FILE
    if not ignore_file.exists():
        return []
    patterns = []
    for line in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.split("#", 1)[0].strip()  # 支持整行注释与行尾注释
        if not line:
            continue
        patterns.append(_normalize_rel(line))
    return patterns


def is_ignored(rel, patterns: list[str]) -> bool:
    """路径是否命中 .secretignore（精确路径或 fnmatch glob）。"""
    rel = _normalize_rel(rel)
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def scan_file(filepath: Path) -> list:
    """扫描单个文件，返回 [(行号, 模式名, 匹配内容, 行内容)]"""
    results = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        for lineno, line in enumerate(content.splitlines(), 1):
            for pattern, name in PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for m in matches:
                    matched = m.group(0)
                    if is_placeholder(matched):
                        continue
                    results.append((lineno, name, matched[:80], line.strip()[:120]))
    except Exception:
        pass
    return results

# SAST 规则（代码级安全问题，与密钥无关）
SAST_PATTERNS = [
    (r'AviatorEvaluator\.execute\s*\(', '全局 AviatorEvaluator.execute（未走禁特性沙箱）'),
    (r'\b(?:execute|executeUpdate|executeQuery|queryForObject|query)\s*\(\s*"'
     r'[^"]*(?:SELECT|INSERT|UPDATE|DELETE|select|insert|update|delete)[^"]*"\s*\+', 'SQL 字符串拼接'),
    (r'\b(?:execute|executeUpdate|executeQuery|queryForObject|query)\s*\(\s*f["\']'
     r'[^"\']*(?:SELECT|INSERT|UPDATE|DELETE|select|insert|update|delete)', 'f-string 拼 SQL'),
    (r'Runtime\.getRuntime\s*\(\s*\)\s*\.exec\s*\(', 'Runtime.exec 命令执行'),
    (r'\bos\.system\s*\(', 'os.system 命令执行'),
    (r'subprocess\.(?:run|Popen|call|check_output)\s*\([^)]*shell\s*=\s*True', 'subprocess shell=True'),
]

SAST_SKIP_KEYWORDS = ('test', 'tests', '_test', 'case', 'cases', 'e2e', 'spec', 'specs',
                      '测试', '冒烟', '联调', 'verify', 'repro', 'probe')

SAST_EXTS = {'.java', '.py', '.kt', '.js', '.ts'}


def scan_sast_file(filepath: Path) -> list:
    """SAST 单文件扫描，返回 [(行号, 规则名, 行内容)]"""
    results = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return results
    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(('//', '#', '*', '/*')):
            continue  # 注释行跳过，减少误报
        for pattern, name in SAST_PATTERNS:
            if re.search(pattern, line):
                results.append((lineno, name, stripped[:120]))
    return results


def git_visible_files(root: Path):
    """仓库根目录时返回 git 可见文件集合（tracked + untracked 未被 ignore），
    让本地扫全仓与 CI 干净检出口径一致；非仓库根目录 / 无 git 返回 None（保持原行为）。"""
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        if top.returncode != 0:
            return None
        if Path(top.stdout.strip()).resolve() != root:
            return None
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, timeout=30)
        if out.returncode != 0:
            return None
        items = out.stdout.decode("utf-8", "replace").split("\0")
        return {i.replace("\\", "/").casefold() for i in items if i}
    except Exception:
        return None


def run_sast(root_dir: str) -> int:
    """代码级 SAST，返回 0 通过 / 1 有问题"""
    root = Path(root_dir).resolve()
    visible = git_visible_files(root)
    findings = []
    scanned = 0
    for filepath in root.rglob('*'):
        if not filepath.is_file() or filepath.suffix.lower() not in SAST_EXTS:
            continue
        if any(d in filepath.parts for d in EXCLUDE_DIRS):
            continue
        if visible is not None and filepath.relative_to(root).as_posix().casefold() not in visible:
            continue
        rel = str(filepath.relative_to(root)).lower()
        if any(kw in rel for kw in SAST_SKIP_KEYWORDS):
            continue
        scanned += 1
        results = scan_sast_file(filepath)
        if results:
            findings.append((filepath.relative_to(root), results))

    print(f"\n=== SAST 代码级扫描（{scanned} 个源文件 / {len(SAST_PATTERNS)} 条规则）===")
    if not findings:
        print("✅ 未发现已知代码级风险模式")
        return 0

    total = sum(len(r) for _, r in findings)
    print(f"❌ 发现 {total} 处代码级风险：\n")
    for filepath, results in findings:
        print(f"📄 {filepath}")
        for lineno, name, line in results:
            print(f"   行{lineno:4d} | {name}")
            print(f"         | {line}")
        print()
    print("⚠️  SAST 命中需逐条确认：真实注入风险按 P0/P1 修复，误报写进安全扫描报告豁免说明。")
    return 1


def main(root_dir: str):
    root = Path(root_dir).resolve()
    visible = git_visible_files(root)
    real_results = []   # 生产代码 / 运维脚本中的疑似密钥 → 阻塞
    test_results = []   # 测试目录中的命中 → 仅警告，需人工确认
    exempt_files = []
    ignore_patterns = load_secretignore(root)
    ignored_files = []  # .secretignore 命中的测试夹具/示例 → 不阻塞
    if visible is not None:
        print(f"ℹ️  仓库根目录：按 git 可见文件扫描（{len(visible)} 个），"
              f"跳过未跟踪 / .gitignore 排除的目录（与 CI 干净检出口径一致）")

    for filepath in root.rglob('*'):
        if filepath.is_dir():
            continue
        if any(d in filepath.parts for d in EXCLUDE_DIRS):
            continue
        if filepath.suffix.lower() in EXCLUDE_EXTS:
            continue
        if visible is not None and filepath.relative_to(root).as_posix().casefold() not in visible:
            continue
        results = scan_file(filepath)
        if not results:
            continue
        rel = filepath.relative_to(root)
        if is_ignored(rel, ignore_patterns):
            ignored_files.append(rel)
            print(f"⏭️ 忽略（.secretignore）: {_normalize_rel(rel)}")
            continue
        if is_test_context(filepath, root):
            test_results.append((rel, results))
            exempt_files.append(str(rel))
        else:
            real_results.append((rel, results))

    if test_results:
        print(f"⚠️  [测试上下文] {len(test_results)} 个文件命中密码/密钥模式（不阻塞，但必须逐条确认是测试账号而非真实密钥）：\n")
        for filepath, results in test_results:
            print(f"📄 {filepath}")
            for lineno, name, matched, line in results:
                print(f"   行{lineno:4d} | {name:20s} | [测试上下文] {matched[:60]}")
            print()
        print("   确认口径：测试账号/临时数据 → 报告里写「已确认为测试账号」；真实密钥 → 按生产代码 P0/P1 修复。")
        print(f"   豁免清单（仅按目录段判定，运维脚本不在此列）：{', '.join(exempt_files[:10])}"
              + (" …" if len(exempt_files) > 10 else ""))
        print()

    if not real_results:
        print("✅ 生产代码未发现硬编码密钥或敏感信息")
        if ignored_files:
            print(f"⏭️  .secretignore 已忽略 {len(ignored_files)} 个测试夹具/示例文件（未参与阻塞判定）")
        print("建议：如果项目已提交 Git，建议再用 `git log --all --source --full-history -S '<关键词>'` 检查历史记录")
        return 0

    total = sum(len(r) for _, r in real_results)
    print(f"❌ 生产代码发现 {total} 处疑似敏感信息泄露：\n")
    for filepath, results in real_results:
        print(f"📄 {filepath}")
        for lineno, name, matched, line in results:
            print(f"   行{lineno:4d} | {name:20s} | {matched}")
            print(f"         | {line}")
        print()

    if ignored_files:
        print(f"⏭️  .secretignore 已忽略 {len(ignored_files)} 个测试夹具/示例文件（未计入上方阻塞）")
    print("⚠️  发现硬编码密钥 / 敏感信息！必须在进入第 9 步前修复：")
    print("   1. 把真实密钥移到 .env 文件，代码中只读环境变量")
    print("   2. 把 .env 加入 .gitignore")
    print("   3. 如果密钥已提交到 Git，立即重置密钥")
    return 1

def _force_utf8_output():
    """Windows 默认 cp936/GBK 控制台下打印中文/emoji 会 UnicodeEncodeError；入口处统一切 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == '__main__':
    _force_utf8_output()
    ap = argparse.ArgumentParser(description='安全扫描：密钥/敏感信息 + 可选 SAST')
    ap.add_argument('root', nargs='?', default='.', help='项目根目录')
    ap.add_argument('--sast', action='store_true', help='追加代码级 SAST 规则')
    a = ap.parse_args()
    code = main(a.root)
    if a.sast:
        code = max(code, run_sast(a.root))
    sys.exit(code)
