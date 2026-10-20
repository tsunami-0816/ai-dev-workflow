#!/usr/bin/env python3
"""
P0 自动化回归测试脚本（把第 8 步的 P0 用例沉淀为可重复运行的脚本）
使用方法：
  1. 在第 8 步全量测试时，把 P0 用例按下方格式写入 p0_cases.json
  2. 回归时运行：python scripts/p0_regression_test.py p0_cases.json
  3. 脚本输出每个用例通过/失败，代替人工一条条手点

用例格式（p0_cases.json）：
[
  {
    "id": "P0-001",
    "name": "登录接口返回 token",
    "method": "POST",
    "url": "http://localhost:8000/auth/login",
    "headers": {"Content-Type": "application/json"},
    "body": {"username": "admin", "password": "admin123"},
    "expect_status": 200,
    "expect_json_contains": ["access_token"]
  }
]
"""

import json
import sys
import time
import urllib.request
import urllib.error


def _json_get(obj, path: str):
    """按点路径取值，如 data.access_token。找不到返回 None。"""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _do_request(method, url, headers, body, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", errors="ignore") if e.fp else "")


def obtain_tokens(auth_cfg) -> dict:
    """预取多角色 token。
    auth_cfg 两种形式：
      - 单角色：{"url":..., "body":..., "token_path":...} → 存入 tokens["default"]
      - 多角色：{"admin": {...}, "employee": {...}, ...} → 存入对应 key
    """
    tokens = {}
    if isinstance(auth_cfg, dict) and "url" in auth_cfg:
        tokens["default"] = _login_one(auth_cfg)
    elif isinstance(auth_cfg, dict):
        for role, cfg in auth_cfg.items():
            tokens[role] = _login_one(cfg)
    return tokens


def _login_one(cfg: dict) -> str:
    method = cfg.get("method", "POST").upper()
    headers = dict(cfg.get("headers", {"Content-Type": "application/json"}))
    body = cfg.get("body")
    token_path = cfg.get("token_path", "data.access_token")
    status, text = _do_request(method, cfg["url"], headers, body, timeout=30)
    if status >= 400:
        raise RuntimeError(f"P0 登录失败 HTTP {status}: {text[:200]}")
    try:
        data = json.loads(text)
    except Exception:
        raise RuntimeError(f"P0 登录响应非 JSON: {text[:200]}")
    token = _json_get(data, token_path)
    if not token:
        raise RuntimeError(f"P0 登录响应中找不到 token 路径 {token_path}: {text[:200]}")
    return token


def run_case(case: dict, tokens: dict = None) -> dict:
    tokens = tokens or {}
    url = case["url"]
    method = case.get("method", "GET").upper()
    headers = dict(case.get("headers", {}))
    body = case.get("body")
    expect_status = case.get("expect_status", 200)
    expect_contains = case.get("expect_json_contains", [])

    # 自动注入 Bearer token：用例可用 auth_as 指定角色，否则取 default；
    # 显式带 Authorization 头的用例（如测无 token 场景）不覆盖。
    if "Authorization" not in headers:
        role = case.get("auth_as") or ("default" if "default" in tokens else next(iter(tokens), None))
        tok = tokens.get(role) if role else None
        if tok:
            headers["Authorization"] = f"Bearer {tok}"

    # 带 body 的请求默认按 JSON 发送，除非用例显式指定了 Content-Type（如 multipart）
    if body is not None and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    start = time.time()
    try:
        status, text = _do_request(method, url, headers, body)
    except Exception as e:
        return {"id": case["id"], "name": case["name"], "passed": False,
                "reason": f"请求异常: {e}"}
    elapsed = time.time() - start

    if status != expect_status:
        return {"id": case["id"], "name": case["name"], "passed": False,
                "reason": f"期望状态码 {expect_status}，实际 {status}，返回: {text[:200]}"}

    missing = [k for k in expect_contains if k not in text]
    if missing:
        return {"id": case["id"], "name": case["name"], "passed": False,
                "reason": f"返回体缺少字段 {missing}，返回: {text[:200]}"}

    return {"id": case["id"], "name": case["name"], "passed": True,
            "elapsed_ms": round(elapsed * 1000)}


def main(cases_file: str):
    raw = json.loads(open(cases_file, encoding="utf-8").read())

    # 兼容两种格式：
    #   1. 旧版纯列表：[{id,name,...}, ...]（无鉴权）
    #   2. 新版带登录：{"auth": {...}, "cases": [...]}（auth 可为单角色或多角色）
    if isinstance(raw, list):
        tokens = {}
        cases = raw
    else:
        tokens = {}
        cases = raw.get("cases", [])
        if raw.get("auth"):
            try:
                tokens = obtain_tokens(raw["auth"])
            except Exception as e:
                print(f"⚠️  自检：登录阶段失败——{e}")
                print("   这不是产品 Bug，是环境问题：后端没起、登录接口 url 错了、或测试账号密码不对。")
                print("   请先确认后端服务在跑、登录配置正确，再跑回归。")
                return 2

    # ===== 自检 1：用例列表不能为空 =====
    if not cases:
        print("⚠️  脚本异常：用例列表为空。请检查 p0_cases.json 格式是否正确。")
        return 2

    results = [run_case(c, tokens) for c in cases]

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    print(f"\n{'='*50}")
    print(f"P0 回归测试：{passed}/{len(results)} 通过" + (f"（已登录取 {len(tokens)} 个角色 token）" if tokens else "（无鉴权）"))
    print(f"{'='*50}")
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        extra = f"（{r.get('elapsed_ms')}ms）" if r["passed"] else f"— {r.get('reason')}"
        print(f"{mark} {r['id']} {r['name']} {extra}")

    # ===== 自检 2：大面积失败时先怀疑环境/脚本，不要直接判产品 Bug =====
    if failed > 0 and failed / len(results) > 0.5:
        # 统计失败类型：连接异常类（ConnectionRefused/timeout）集中出现 → 环境问题
        conn_errors = sum(
            1 for r in results
            if (not r["passed"]) and ("连接" in r.get("reason", "") or "refused" in r.get("reason", "").lower() or "timed out" in r.get("reason", "").lower() or "Max retries" in r.get("reason", ""))
        )
        print(f"\n⚠️  警告：失败 {failed}/{len(results)} = {failed/len(results):.0%}，超过一半。")
        if conn_errors == failed:
            print("   所有失败都是「连接被拒绝/超时」——这不是产品 Bug，是后端服务根本没起来，")
            print("   或者用例里的 url 端口/路径写错了。请先确认服务在跑，再重新跑回归。")
        else:
            print("   真实项目经验：这种情况优先怀疑三件事，再改产品代码：")
            print("   ① 后端服务真的在跑吗？健康检查通吗？")
            print("   ② 用例 url / 请求体是针对当前版本写的吗？接口路径最近改过没有？")
            print("   ③ 脚本对返回体的解析路径对吗？抽 1 个失败用例用 curl 直接打一下肉眼看返回。")
            print("   确认是产品真 Bug 再修，否则大概率是脚本/环境假失败。")

    # 生成报告文件
    report = {
        "total": len(results), "passed": passed, "failed": failed,
        "cases": results
    }
    report_path = cases_file.replace(".json", "_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存：{report_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/p0_regression_test.py <p0_cases.json>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
