#!/usr/bin/env python3
"""
接口契约一致性校验脚本（解决前后端接口对不上问题）
用法：
  1. 后端启动后自动导出 OpenAPI：python scripts/api_contract_validator.py export http://localhost:8000/openapi.json 06.5_契约/openapi.json
  2. 校验前端代码调用是否符合契约：python scripts/api_contract_validator.py check 06.5_契约/openapi.json <前端代码目录>
     可选扩展：
       --headers X-Tenant-Id,X-Internal-Token   校验契约里是否声明了这些必带请求头
       --aliases payload=_payload               扫描代码里字段别名是否跨文件漂移
       --scan-dir <后端代码目录>                别名扫描的目录（默认取前端目录的父级项目根）
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

HTTP_METHODS = ("get", "post", "put", "delete", "patch")
SOURCE_SUFFIX = {".java", ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".kt"}
SCAN_SKIP_DIRS = {"node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", ".git"}


def export_openapi(url: str, out_path: str):
    """从运行中的后端导出 OpenAPI 契约"""
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = data.get("paths", {})
    print(f"✅ 契约已导出到 {out_path}")
    print(f"   共 {len(paths)} 个接口路径")
    for p in sorted(paths):
        methods = ",".join(m.upper() for m in paths[p] if m in ("get", "post", "put", "delete", "patch"))
        print(f"   {methods:20s} {p}")
    return 0


def _norm(path: str) -> str:
    """归一化路径参数，便于跨写法比对：
    /tickets/{ticket_id}、/tickets/${id}、/tickets/:id、/documents/12 统一成 /tickets/{id}、/documents/{id}"""
    path = path.split("?")[0]  # 前端调用常带 query string（如 /api/metrics/summary?range_days=7），比对前必须剥离，否则误报「臆造接口」
    path = re.sub(r"\$\{[^}]+\}", "{id}", path)
    path = re.sub(r"\{[^}]+\}", "{id}", path)
    path = re.sub(r"/:[^/]+", "/{id}", path)
    path = re.sub(r"/\d+", "/{id}", path)
    return path.rstrip("/") or "/"


def _api_segments(valid_paths: set, prefixes: list) -> set:
    """从契约动态推导 API 首段集合（替代原先硬编码 /tickets|/documents 等项目专属清单）：
    契约原始首段（如 api、internal）+ 剥离公共前缀后的相对首段（如 auth、workflows）。"""
    segs = set()
    for p in valid_paths:
        parts = [s for s in p.split("/") if s]
        if parts:
            segs.add(parts[0])
        for pre in prefixes:
            if p.startswith(pre + "/"):
                rest = [s for s in p[len(pre):].split("/") if s]
                if rest:
                    segs.add(rest[0])
    return segs


def _shared_prefixes(valid_paths: set, threshold: float = 0.8) -> list:
    """找出被绝大多数后端接口共享的挂载前缀（例如统一挂载前缀 /api）。

    前端通常把这个前缀写进 base_url，调用处只写相对路径（如 "/auth/login"），
    因此比对前必须先剥离公共前缀，否则会把真实存在的接口全部误判为「臆造接口」。"""
    counter: dict = {}
    total = 0
    for p in valid_paths:
        segs = [s for s in p.split("/") if s]
        if not segs:
            continue
        total += 1
        for k in range(1, len(segs)):
            pre = "/" + "/".join(segs[:k])
            counter[pre] = counter.get(pre, 0) + 1
    if total == 0:
        return []
    return [pre for pre, cnt in counter.items() if cnt >= total * threshold]


def check_frontend(contract_path: str, frontend_dir: str):
    """检查前端代码中的接口调用是否都存在于契约中"""
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    valid_paths = set(contract.get("paths", {}).keys())
    norm_contract = {_norm(p): p for p in valid_paths}
    prefixes = _shared_prefixes(valid_paths)

    # ===== 自检 1：契约本身是否解析正常 =====
    if len(valid_paths) == 0:
        print("⚠️  脚本异常：契约文件里 paths 为空。")
        print("   OpenAPI 导出可能失败，或后端尚未注册任何路由。")
        print("   请先检查后端是否真的在跑、openapi.json 内容是否正常。")
        return 2

    frontend = Path(frontend_dir)
    # 匹配前端代码中的 API 调用路径：首段集合从契约动态推导，避免项目专属硬编码漏抓
    segments = sorted(_api_segments(valid_paths, prefixes), key=len, reverse=True)
    if not segments:
        print("⚠️  脚本异常：无法从契约推导 API 首段集合。")
        return 2
    api_pattern = re.compile(r'["\'`](/(?:' + "|".join(re.escape(s) for s in segments) + r')[^"\'`\s]*)["\'`]')

    # 排除前端页面路由/菜单/跳转路径（不是 API 调用）：
    # path: '/mqtt-subscriptions'、to="/x"、redirect: '/x'、router.push(`/workflows/${id}/edit`)
    # 2026-10-31 修复：这些写法与 API 路径同样以 / 开头，会误报「前端臆造接口」
    nav_pattern = re.compile(
        r'(?:path|redirect|to|index)\s*[:=]\s*[`"\'](?:[^`"\']*)[`"\']'
        r'|(?:router\.)?push\s*\(\s*[`"\'](?:[^`"\']*)[`"\']'
    )

    calls = {}
    scanned_files = 0
    for f in frontend.rglob("*"):
        if f.is_dir() or f.suffix not in (".js", ".jsx", ".ts", ".tsx", ".vue", ".py"):
            continue
        # router/ 目录放的是前端页面路由（如 /workflows/:id/edit），不是 API 调用，排除防误报
        if any(d in f.parts for d in ("node_modules", "dist", "build", "__pycache__", "router")):
            continue
        scanned_files += 1
        text = f.read_text(encoding="utf-8", errors="ignore")
        text = nav_pattern.sub("", text)
        for m in api_pattern.finditer(text):
            path = _norm(m.group(1))  # 归一化路径参数
            calls.setdefault(path, []).append(str(f.relative_to(frontend)))

    # baseURL 本身（如 '/api/v1'）不是接口调用，剔除公共前缀精确匹配项
    for pre in prefixes:
        calls.pop(_norm(pre), None)

    # ===== 自检 2：前端是否真的解析到了调用 =====
    if scanned_files == 0:
        print(f"⚠️  脚本异常：在 {frontend_dir} 下没有找到任何 .js/.jsx/.ts/.tsx/.vue/.py 源文件。")
        print("   请确认前端目录路径是否正确。")
        return 2
    if len(calls) == 0:
        print("⚠️  脚本异常：扫描了 {} 个前端源文件，但正则没匹配到任何 API 调用。".format(scanned_files))
        print("   本脚本的正则是针对常见写法（/api/xxx、/auth/xxx 等硬编码路径）写的，")
        print("   如果你的前端把 baseURL 配在 axios/fetch 实例里、调用处只写 '/xxx'，")
        print("   正则可能抓不到。请人工确认后再下结论，不要直接判「前端零调用」。")
        return 2

    print(f"=== 前端接口调用校验（对照 {contract_path}）===")
    print(f"   自检：契约 {len(valid_paths)} 个路径 / 扫描 {scanned_files} 个源文件 / 解析出 {len(calls)} 个不同调用\n")
    if prefixes:
        print(f"ℹ️ 检测到后端统一挂载前缀 {prefixes}，比对时自动剥离（前端通常把该前缀写在 base_url 中）\n")
    missing = []
    for path, files in sorted(calls.items()):
        hit = norm_contract.get(path)
        # 剥离公共前缀后重试：前端调用 "/auth/login" ↔ 契约 "/api/auth/login"
        if not hit:
            for pre in prefixes:
                hit = norm_contract.get(_norm(pre + path))
                if hit:
                    break
        if hit:
            print(f"  ✅ {path}  →  {hit}")
        else:
            missing.append(path)
            print(f"  ❌ {path}  ← 契约中不存在（前端臆造接口？）")
            for f in set(files):
                print(f"      调用位置: {f}")

    print(f"\n前端共调用 {len(calls)} 个不同接口，{len(missing)} 个不在契约中")

    # ===== 自检 3：大面积报红时警告先怀疑脚本 =====
    if len(calls) > 0 and len(missing) / len(calls) > 0.5:
        print(f"\n⚠️  警告：报红比例 {len(missing)}/{len(calls)} = {len(missing)/len(calls):.0%}，超过一半。")
        print("   真实项目经验：这种情况大概率是脚本路径解析问题（如挂载前缀未识别、")
        print("   前端 base_url 配置导致路径写法不一致），而不是真的有这么多臆造接口。")
        print("   请先人工抽 1~2 个报红项：打开对应前端文件和 OpenAPI 文档肉眼核对，")
        print("   确认是真不一致再修前端，是脚本问题就修脚本。")
    return 1 if missing else 0


def check_headers(contract_path: str, required: list[str]) -> list[str]:
    """校验必带请求头是否在契约中声明（漏声明 = 跨服务调用漏传的高风险）"""
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    paths = contract.get("paths", {})
    print("\n=== 必带请求头校验 ===")
    problems = []
    for header in required:
        declared, missing = [], []
        for p, item in paths.items():
            for method, op in item.items():
                if method not in HTTP_METHODS or not isinstance(op, dict):
                    continue
                params = op.get("parameters") or []
                has = any(
                    isinstance(pr, dict) and pr.get("in") == "header"
                    and str(pr.get("name", "")).lower() == header.lower()
                    for pr in params
                )
                (declared if has else missing).append(f"{method.upper()} {p}")
        print(f"  {header}: {len(declared)} 个接口已声明，{len(missing)} 个未声明")
        if not declared:
            problems.append(f"{header} 在契约中完全没有声明（header 参数漏写，或该头由网关注入需人工确认）")
        elif missing:
            for m in missing[:10]:
                print(f"    ⚠️ 未声明: {m}")
            if len(missing) > 10:
                print(f"    ... 共 {len(missing)} 个未声明（由网关统一注入的接口可忽略）")
    return problems


def _scan_sources(scan_dir: Path) -> dict:
    """读取目录下源码文件内容：{相对路径: 文本}（os.walk 剪枝，避免遍历 node_modules）"""
    import os
    texts = {}
    for current, dirs, files in os.walk(scan_dir):
        dirs[:] = [d for d in dirs if d not in SCAN_SKIP_DIRS]
        for name in files:
            f = Path(current) / name
            if f.suffix not in SOURCE_SUFFIX:
                continue
            try:
                texts[str(f.relative_to(scan_dir))] = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return texts


def check_aliases(scan_dir: str, alias_pairs: list[str]) -> list[str]:
    """字段别名跨文件漂移检测：同一语义出现两种写法（如 payload / _payload）时告警"""
    root = Path(scan_dir)
    if not root.exists():
        return [f"别名扫描目录不存在: {scan_dir}"]
    print("\n=== 字段别名一致性校验 ===")
    texts = _scan_sources(root)
    print(f"   扫描 {len(texts)} 个源码文件")
    problems = []
    for pair in alias_pairs:
        if "=" not in pair:
            problems.append(f"别名参数格式错误（应为 a=b）: {pair}")
            continue
        a, b = [x.strip() for x in pair.split("=", 1)]
        files_a = sorted(k for k, v in texts.items() if re.search(rf"\b{re.escape(a)}\b", v))
        files_b = sorted(k for k, v in texts.items() if re.search(rf"\b{re.escape(b)}\b", v))
        if files_a and files_b:
            overlap = set(files_a) & set(files_b)
            print(f"  ⚠️  {a} 与 {b} 同时出现：{a} {len(files_a)} 文件 / {b} {len(files_b)} 文件 / 重叠 {len(overlap)}")
            if not overlap:
                problems.append(
                    f"别名漂移嫌疑: {a} 只在 {files_a[:3]} 出现，{b} 只在 {files_b[:3]} 出现，两处代码没有任何文件同时使用——读写可能对不上")
            else:
                print("    ✅ 存在同时使用两种写法的文件，回归兼容风险较低（仍需人工确认读写一致）")
        elif files_a or files_b:
            print(f"  ✅ 只存在一种写法（{a if files_a else b}），无漂移")
        else:
            print(f"  ℹ️  两种写法均未出现，确认别名配置是否已废弃")
    return problems


def run_check(contract_path: str, frontend_dir: str, headers: list[str] | None = None,
              aliases: list[str] | None = None, scan_dir: str | None = None) -> int:
    code = check_frontend(contract_path, frontend_dir)
    problems = []
    if headers:
        problems.extend(check_headers(contract_path, headers))
    if aliases:
        base = scan_dir or str(Path(frontend_dir).parent)
        problems.extend(check_aliases(base, aliases))
    if problems:
        print("\n❌ 契约扩展校验发现 %d 个问题:" % len(problems))
        for p in problems:
            print(f"  - {p}")
        return 1
    if headers or aliases:
        print("\n✅ 契约扩展校验通过")
    return code


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "export":
        sys.exit(export_openapi(sys.argv[2], sys.argv[3]))
    elif cmd == "check":
        ap = argparse.ArgumentParser(description="接口契约一致性校验")
        ap.add_argument("contract")
        ap.add_argument("frontend")
        ap.add_argument("--headers", default="", help="必带请求头，逗号分隔")
        ap.add_argument("--aliases", default="", help="字段别名对，格式 a=b，可逗号分隔多组")
        ap.add_argument("--scan-dir", default=None, help="别名扫描目录（默认前端目录的父级）")
        a = ap.parse_args(sys.argv[2:])
        header_list = [h.strip() for h in a.headers.split(",") if h.strip()]
        alias_list = [p.strip() for p in a.aliases.split(",") if p.strip()]
        sys.exit(run_check(a.contract, a.frontend, header_list, alias_list, a.scan_dir))
    else:
        print(__doc__)
        sys.exit(1)
