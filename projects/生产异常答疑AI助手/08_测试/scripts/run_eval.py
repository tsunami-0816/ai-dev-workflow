"""离线评估脚本：遍历黄金测试用例，调用问答编排，输出分级准确率/响应时间/来源覆盖率。
用法（从项目根运行）：
    python "projects/生产异常答疑AI助手/08_测试/scripts/run_eval.py"
（需先运行 backend/scripts/init_db.py 并启动模型；可在后端未启动时直接运行，走 service 层。）
"""
import json
import os
import sys
import time

# 脚本在 08_测试/scripts/，往上三级到项目根，再拼 05_代码/backend
_BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "05_代码", "backend",
)
sys.path.insert(0, _BACKEND)

from app.db.session import SessionLocal  # noqa: E402
from app.models import QATestCase, User  # noqa: E402
from app.schemas.chat import AskRequest  # noqa: E402
from app.services import ask_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "employee").first()
        if not user:
            print("未找到 employee 账号，请先运行 python scripts/init_db.py")
            return
        cases = db.query(QATestCase).all()
        if not cases:
            print("无黄金测试用例")
            return

        results = []
        route_correct = 0
        severity_correct = 0
        total_ms = 0
        source_count = 0
        ticket_count = 0

        for c in cases:
            t0 = time.time()
            try:
                resp = ask_service.ask(db, user, AskRequest(question=c.question))
                ms = int((time.time() - t0) * 1000)
                route_ok = resp.route_result == c.expected_route
                sev_ok = bool(resp.grading) and resp.grading.severity == c.severity
                has_source = len(resp.sources) > 0
                if route_ok:
                    route_correct += 1
                if sev_ok:
                    severity_correct += 1
                if has_source:
                    source_count += 1
                if resp.need_ticket:
                    ticket_count += 1
                total_ms += ms
                results.append(
                    {
                        "question": c.question,
                        "expected_route": c.expected_route,
                        "actual_route": resp.route_result,
                        "route_ok": route_ok,
                        "expected_severity": c.severity,
                        "actual_severity": resp.grading.severity if resp.grading else None,
                        "ms": ms,
                        "has_source": has_source,
                        "ticket_id": resp.ticket_id,
                    }
                )
                flag = "OK" if route_ok else "XX"
                print(f"[{flag}] {c.question[:32]:<32} -> {resp.route_result:6} ({ms}ms)")
            except Exception as e:
                print(f"[ERR] {c.question[:32]:<32} -> {e}")
                results.append({"question": c.question, "error": str(e)})

        n = len(cases)
        summary = {
            "cases": n,
            "route_accuracy": round(route_correct / n, 4) if n else 0,
            "severity_accuracy": round(severity_correct / n, 4) if n else 0,
            "avg_response_ms": round(total_ms / n, 1) if n else 0,
            "source_coverage": round(source_count / n, 4) if n else 0,
            "ticket_rate": round(ticket_count / n, 4) if n else 0,
        }
        print("\n===== 评估报告 =====")
        print(f"用例数: {n}")
        print(f"分级/路由准确率: {route_correct}/{n} = {summary['route_accuracy']*100:.1f}%")
        print(f"严重等级准确率: {severity_correct}/{n} = {summary['severity_accuracy']*100:.1f}%")
        print(f"平均响应时间: {summary['avg_response_ms']:.0f}ms")
        print(f"答案带来源比例: {source_count}/{n} = {summary['source_coverage']*100:.1f}%")
        print(f"派单比例: {ticket_count}/{n} = {summary['ticket_rate']*100:.1f}%")

        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "eval_report.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "details": results}, f, ensure_ascii=False, indent=2)
        print(f"\n详细报告已写入: {out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
