"""效果评估（admin）：黄金测试用例展示 + 离线评估指引。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_admin, sidebar

st.set_page_config(page_title="效果评估", page_icon="📊", layout="wide")
require_admin()
sidebar()

st.markdown("# 📊 效果评估")
st.caption("黄金测试用例与离线评估指标；批量评估请在后端目录运行脚本")

# 评估指引
with st.expander("🧪 如何运行批量评估", expanded=True):
    st.markdown(
        "在后端目录执行：\n\n"
        "```bash\n"
        "cd backend\n"
        "python eval/run_eval.py\n"
        "```\n\n"
        "脚本会遍历黄金测试用例，调用问答编排，输出：\n"
        "- 分级/路由准确率（目标 ≥85%）\n"
        "- 严重等级准确率\n"
        "- 平均响应时间（目标 ≤30 秒）\n"
        "- 答案带来源比例（目标 100%）\n"
        "- 派单比例\n\n"
        "详细结果写入 `backend/eval/eval_report.json`。"
    )

st.divider()

# 黄金用例列表
st.markdown("### 黄金测试用例")
try:
    data = api_client.list_cases(page_size=200)
    cases = data.get("list", [])
    total = data.get("total", 0)
except ApiError as e:
    st.error(e.message)
    cases = []
    total = 0

st.caption(f"共 {total} 条用例")

if cases:
    # 按场景统计
    scenario_stats = {}
    route_stats = {"answer": 0, "ticket": 0}
    for c in cases:
        s = c.get("scenario", "其他")
        scenario_stats[s] = scenario_stats.get(s, 0) + 1
        route_stats[c.get("expected_route", "answer")] = route_stats.get(c.get("expected_route", "answer"), 0) + 1

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**按场景分布**")
        for s, n in scenario_stats.items():
            st.markdown(f"- {s}：{n} 条")
    with col2:
        st.markdown("**预期路由分布**")
        st.markdown(f"- 直接回答：{route_stats.get('answer',0)} 条")
        st.markdown(f"- 派单：{route_stats.get('ticket',0)} 条")

    st.divider()
    for c in cases:
        severity_color = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(c.get("severity"), "⚪")
        route_label = "📖 直接回答" if c.get("expected_route") == "answer" else "📋 派单"
        with st.container(border=True):
            st.markdown(f"{severity_color} **[{c.get('severity')}]** {c.get('question','')}")
            st.caption(f"场景: {c.get('scenario','')} ｜ 预期路由: {route_label}")
            if c.get("standard_answer"):
                st.markdown(f"**参考答案：** {c['standard_answer']}")
