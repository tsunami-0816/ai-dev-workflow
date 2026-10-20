#!/usr/bin/env python3
"""
依赖版本真实性校验脚本（专治 AI 幻觉依赖）
解析 requirements.txt / package.json / pom.xml，批量查询版本是否真实存在
使用方法：python scripts/dependency_checker.py <项目根目录>
"""

import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

TIMEOUT = 10


def query_pypi(package: str, version: str) -> bool:
    """查询 PyPI 验证包和版本是否存在"""
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        # 包存在但版本不存在时，再查一次包是否存在
        try:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=TIMEOUT) as resp2:
                return False  # 包存在，版本不存在
        except Exception:
            return False  # 包也不存在
    except Exception:
        return None  # 网络问题，无法判断


def query_npm(package: str, version: str) -> bool:
    """查询 npm registry 验证包和版本是否存在"""
    url = f"https://registry.npmjs.org/{package}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            versions = data.get("versions", {})
            return version in versions
    except Exception:
        return None


def query_maven(group: str, artifact: str, version: str) -> bool:
    """查询 Maven Central 验证"""
    g = group.replace(".", "/")
    url = f"https://repo1.maven.org/maven2/{g}/{artifact}/{version}/"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return None


def parse_requirements_txt(filepath: Path) -> list:
    """解析 requirements.txt，返回 [(name, version)]"""
    deps = []
    for line in filepath.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"([a-zA-Z0-9_\-\.]+)\s*==\s*([a-zA-Z0-9\.\*\+]+)", line)
        if m:
            deps.append((m.group(1), m.group(2)))
        else:
            m2 = re.match(r"([a-zA-Z0-9_\-\.]+)\s*([<>=!~]+)\s*([a-zA-Z0-9\.\*]+)", line)
            if m2:
                deps.append((m2.group(1), m2.group(3) + " (范围:" + m2.group(2) + ")"))
    return deps


def parse_package_json(filepath: Path) -> list:
    """解析 package.json，返回 [(name, version)]"""
    deps = []
    data = json.loads(filepath.read_text(encoding="utf-8", errors="ignore"))
    for section in ("dependencies", "devDependencies"):
        for name, ver in data.get(section, {}).items():
            clean = re.sub(r"^[\^~>=<]+", "", ver)
            deps.append((name, clean))
    return deps


def parse_pom_xml(filepath: Path) -> list:
    """粗解析 pom.xml，返回 [(group:artifact, version)]"""
    deps = []
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    blocks = re.findall(r"<dependency>(.*?)</dependency>", text, re.DOTALL)
    for b in blocks:
        g = re.search(r"<groupId>(.*?)</groupId>", b)
        a = re.search(r"<artifactId>(.*?)</artifactId>", b)
        v = re.search(r"<version>(.*?)</version>", b)
        if g and a:
            version = v.group(1) if v else "未指定"
            deps.append((f"{g.group(1)}:{a.group(1)}", version))
    return deps


def main(root_dir: str):
    root = Path(root_dir).resolve()
    problems = []
    checked = 0

    # Python
    req = root / "requirements.txt"
    if req.exists():
        print("=== 校验 requirements.txt ===")
        for name, ver in parse_requirements_txt(req):
            checked += 1
            result = query_pypi(name, ver)
            if result is True:
                print(f"  ✅ {name}=={ver}")
            elif result is False:
                problems.append(f"❌ pip: {name}=={ver} 不存在（AI 幻觉依赖？）")
                print(f"  ❌ {name}=={ver} 不存在")
            else:
                print(f"  ⚠️  {name}=={ver} 网络校验失败，请手动确认")

    # Node
    pkg = root / "package.json"
    if pkg.exists():
        print("\n=== 校验 package.json ===")
        for name, ver in parse_package_json(pkg):
            checked += 1
            result = query_npm(name, ver)
            if result is True:
                print(f"  ✅ {name}@{ver}")
            elif result is False:
                problems.append(f"❌ npm: {name}@{ver} 不存在（AI 幻觉依赖？）")
                print(f"  ❌ {name}@{ver} 不存在")
            else:
                print(f"  ⚠️  {name}@{ver} 网络校验失败，请手动确认")

    # Maven
    pom = root / "pom.xml"
    if pom.exists():
        print("\n=== 校验 pom.xml ===")
        for name, ver in parse_pom_xml(pom):
            if "${" in ver:  # 属性引用，跳过
                print(f"  ⏭️  {name}:{ver}（属性引用，跳过）")
                continue
            checked += 1
            g, a = name.split(":", 1)
            result = query_maven(g, a, ver)
            if result is True:
                print(f"  ✅ {name}:{ver}")
            elif result is False:
                problems.append(f"❌ maven: {name}:{ver} 不存在（AI 幻觉依赖？）")
                print(f"  ❌ {name}:{ver} 不存在")
            else:
                print(f"  ⚠️  {name}:{ver} 网络校验失败，请手动确认")

    print(f"\n{'='*40}")
    print(f"共校验 {checked} 个依赖，发现 {len(problems)} 个问题")
    if problems:
        print("\n".join(problems))
        print("\n⚠️  发现 AI 幻觉依赖！请在架构评审阶段修复后再进入开发。")
        return 1
    else:
        print("✅ 全部依赖版本真实存在")
        return 0


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(main(root))
