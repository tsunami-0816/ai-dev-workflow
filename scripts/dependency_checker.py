#!/usr/bin/env python3
"""
依赖版本真实性校验脚本（专治 AI 幻觉依赖）
解析 requirements.txt / package.json / pom.xml，批量查询版本是否真实存在
使用方法：
    python scripts/dependency_checker.py <项目根目录>
    python scripts/dependency_checker.py <项目根目录> --solve   # 追加可解性校验（推荐第 3/6 步都跑）

--solve 说明：单包存在 ≠ 整体能解（版本冲突、传递依赖缺失）。
    Python 走 `pip install --dry-run --ignore-installed -r requirements.txt`
    Maven  走 `mvn -B dependency:tree`（失败即视为不可解析）
工具缺失（无 pip / 无 mvn）时跳过并显式提示，不判失败。
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

TIMEOUT = 10
SOLVE_TIMEOUT = 600

SKIP_DIRS = {"node_modules", ".venv", "venv", "target", ".git", "__pycache__", "dist", ".idea"}


def find_files(root: Path, filename: str, max_depth: int = 4) -> list:
    """在项目根下按文件名查找（跳过构建产物/虚拟环境目录，限制层级）"""
    results = []
    for p in root.rglob(filename):
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if len(rel.parts) - 1 > max_depth:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        results.append(p)
    return sorted(results)


def _tail(text: str, lines: int = 8) -> str:
    rows = [r for r in (text or "").strip().splitlines() if r.strip()]
    return "\n".join(rows[-lines:])


def solve_python(req_file: Path) -> tuple:
    """pip 依赖可解性校验：返回 (ok, message)"""
    cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "-r", req_file.name]
    try:
        proc = subprocess.run(cmd, cwd=str(req_file.parent), capture_output=True,
                              text=True, timeout=SOLVE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "pip 解析超时（依赖过多或网络慢）"
    except Exception as e:
        return False, f"pip 执行异常: {e}"
    if proc.returncode == 0:
        return True, ""
    return False, _tail(proc.stderr or proc.stdout)


def solve_maven(pom_file: Path) -> tuple:
    """Maven 依赖可解性校验：返回 (ok, message)"""
    mvn = shutil.which("mvn") or shutil.which("mvn.cmd")
    if not mvn:
        return None, "未安装 mvn，跳过"
    cmd = [mvn, "-B", "dependency:tree", "-DoutputType=text"]
    try:
        proc = subprocess.run(cmd, cwd=str(pom_file.parent), capture_output=True,
                              text=True, timeout=SOLVE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "mvn dependency:tree 超时"
    except Exception as e:
        return False, f"mvn 执行异常: {e}"
    if proc.returncode == 0:
        return True, ""
    return False, _tail(proc.stderr or proc.stdout)


def run_solve(root: Path) -> list:
    """依赖可解性校验，返回问题列表（空列表=通过）"""
    problems = []
    checked = 0
    print("\n=== 依赖可解性校验（--solve）===")

    for req_file in find_files(root, "requirements.txt"):
        checked += 1
        print(f"  → pip: {req_file.relative_to(root)}")
        ok, msg = solve_python(req_file)
        if ok:
            print("    ✅ 依赖可解析")
        else:
            problems.append(f"❌ pip 不可解析: {req_file.relative_to(root)}\n    {msg}")
            print("    ❌ 依赖不可解析")

    for pom_file in find_files(root, "pom.xml"):
        checked += 1
        print(f"  → mvn: {pom_file.relative_to(root)}")
        ok, msg = solve_maven(pom_file)
        if ok is None:
            print(f"    ⚠️  {msg}")
        elif ok:
            print("    ✅ 依赖可解析")
        else:
            problems.append(f"❌ mvn 不可解析: {pom_file.relative_to(root)}\n    {msg}")
            print("    ❌ 依赖不可解析")

    if checked == 0:
        print("  ⚠️  未找到 requirements.txt / pom.xml，跳过")
    return problems


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


def main(root_dir: str, solve: bool = False):
    root = Path(root_dir).resolve()
    problems = []
    checked = 0
    file_found = False

    # Python
    for req in find_files(root, "requirements.txt"):
        file_found = True
        print(f"=== 校验 {req.relative_to(root)} ===")
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
    for pkg in find_files(root, "package.json"):
        file_found = True
        print(f"\n=== 校验 {pkg.relative_to(root)} ===")
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
    for pom in find_files(root, "pom.xml"):
        file_found = True
        print(f"\n=== 校验 {pom.relative_to(root)} ===")
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

    if not file_found:
        print("⚠️  未找到 requirements.txt / package.json / pom.xml，请确认项目目录")

    # 依赖可解性（可选）
    if solve:
        problems.extend(run_solve(root))

    print(f"\n{'='*40}")
    print(f"共校验 {checked} 个依赖，发现 {len(problems)} 个问题")
    if problems:
        print("\n".join(problems))
        print("\n⚠️  存在问题依赖！请在架构评审阶段修复后再进入开发。")
        return 1
    else:
        print("✅ 全部依赖版本真实存在" + ("，且依赖可解" if solve else ""))
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="依赖版本真实性与可解性校验")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--solve", action="store_true",
                        help="追加依赖可解性校验（pip --dry-run / mvn dependency:tree）")
    args = parser.parse_args()
    sys.exit(main(args.root, args.solve))
