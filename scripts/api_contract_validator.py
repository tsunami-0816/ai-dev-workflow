#!/usr/bin/env python3
"""
接口契约一致性校验脚本（解决前后端接口对不上问题）
用法：
  1. 后端启动后自动导出 OpenAPI：python scripts/api_contract_validator.py export http://localhost:8000/openapi.json 06.5_契约/openapi.json
  2. 校验前端代码调用是否符合契约：python scripts/api_contract_validator.py check 06.5_契约/openapi.json <前端代码目录>
"""

import json
import re
import sys
import urllib.request
from pathlib import Path


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
    /tickets/{ticket_id}、/tickets/${id}、/documents/12 统一成 /tickets/{id}、/documents/{id}"""
    path = re.sub(r"\$\{[^}]+\}", "{id}", path)
    path = re.sub(r"\{[^}]+\}", "{id}", path)
    path = re.sub(r"/\d+", "/{id}", path)
    return path.rstrip("/") or "/"


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
    # 匹配前端代码中的 API 调用路径
    api_pattern = re.compile(r'["\'`](/api/[^"\'`\s]+|/auth/[^"\'`\s]+|/chat/[^"\'`\s]+|/tickets[^"\'`\s]*|/documents[^"\'`\s]*|/notifications[^"\'`\s]*|/conversations[^"\'`\s]*|/users[^"\'`\s]*|/knowledge[^"\'`\s]*|/eval[^"\'`\s]*)["\'`]')

    calls = {}
    scanned_files = 0
    for f in frontend.rglob("*"):
        if f.is_dir() or f.suffix not in (".js", ".jsx", ".ts", ".tsx", ".vue", ".py"):
            continue
        if any(d in f.parts for d in ("node_modules", "dist", "build", "__pycache__")):
            continue
        scanned_files += 1
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in api_pattern.finditer(text):
            path = _norm(m.group(1))  # 归一化路径参数
            calls.setdefault(path, []).append(str(f.relative_to(frontend)))

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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "export":
        sys.exit(export_openapi(sys.argv[2], sys.argv[3]))
    elif cmd == "check":
        sys.exit(check_frontend(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(1)
