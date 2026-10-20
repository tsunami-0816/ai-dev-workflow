#!/usr/bin/env python3
"""
安全扫描：硬编码密钥、密码、Token、数据库连接字符串检测
使用方法：python scripts/security_scan_secrets.py <项目根目录>
"""

import os
import re
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

def is_placeholder(text: str) -> bool:
    """判断是否为占位符而非真实密钥"""
    low = text.lower()
    return any(ph in low for ph in PLACEHOLDERS)

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

def main(root_dir: str):
    root = Path(root_dir).resolve()
    all_results = []

    for filepath in root.rglob('*'):
        if filepath.is_dir():
            continue
        if any(d in filepath.parts for d in EXCLUDE_DIRS):
            continue
        if filepath.suffix.lower() in EXCLUDE_EXTS:
            continue
        results = scan_file(filepath)
        if results:
            all_results.append((filepath.relative_to(root), results))

    if not all_results:
        print("✅ 未发现硬编码密钥或敏感信息")
        print("建议：如果项目已提交 Git，建议再用 `git log --all --source --full-history -S '<关键词>'` 检查历史记录")
        return 0

    total = sum(len(r) for _, r in all_results)
    print(f"❌ 发现 {total} 处疑似敏感信息泄露：\n")
    for filepath, results in all_results:
        print(f"📄 {filepath}")
        for lineno, name, matched, line in results:
            print(f"   行{lineno:4d} | {name:20s} | {matched}")
            print(f"         | {line}")
        print()

    print("⚠️  发现硬编码密钥 / 敏感信息！必须在进入第 9 步前修复：")
    print("   1. 把真实密钥移到 .env 文件，代码中只读环境变量")
    print("   2. 把 .env 加入 .gitignore")
    print("   3. 如果密钥已提交到 Git，立即重置密钥")
    return 1

if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    sys.exit(main(root))
