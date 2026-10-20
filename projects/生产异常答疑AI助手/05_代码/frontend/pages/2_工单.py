"""工单中心：列表、详情、领取、处理、关闭（可选沉淀）。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_login, sidebar

st.set_page_config(page_title="工单中心", page_icon="📋", layout="wide")
require_login()
sidebar()

st.markdown("# 📋 工单中心")
st.caption("查看分配给你的工单，领取、处理并关闭；关闭时可选择沉淀为知识")

# 筛选
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    status_filter = st.selectbox("状态", ["全部", "pending", "processing", "closed"], index=0)
with col2:
    route_filter = st.selectbox("负责人类型", ["全部", "repair", "process", "safety", "admin"], index=0)
with col3:
    if st.button("🔄 刷新", use_container_width=True):
        st.rerun()

status_param = None if status_filter == "全部" else status_filter
route_param = None if route_filter == "全部" else route_filter

try:
    data = api_client.list_tickets(status=status_param, route_type=route_param, page_size=50)
    tickets = data.get("list", [])
    total = data.get("total", 0)
except ApiError as e:
    st.error(e.message)
    tickets = []
    total = 0

st.caption(f"共 {total} 条工单")

if not tickets:
    st.info("暂无工单")
else:
    for t in tickets:
        severity_color = {"P0": "🔴", "P1": "🟠", "P2": "🟡"}.get(t.get("severity"), "⚪")
        status_label = {"pending": "待领取", "processing": "处理中", "closed": "已关闭"}.get(t.get("status"), t.get("status"))
        with st.expander(
            f"{severity_color} [{t.get('severity')}] {t.get('title','')}  ｜  工单号：{t.get('id')}  ｜  "
            f"状态：{status_label}  ｜  负责人：{t.get('assignee_role','')}  ｜  {t.get('created_at','')[:16]}"
        ):
            st.markdown(f"**问题描述：** {t.get('question','')}")
            if t.get("llm_reason"):
                st.caption(f"分级理由：{t['llm_reason']}")
            if t.get("answer_snapshot"):
                st.caption(f"答案快照：{t['answer_snapshot'][:200]}")

            # 处理记录
            try:
                handlings = api_client.list_handlings(t["id"])
                if handlings:
                    st.markdown("**处理记录：**")
                    for h in handlings:
                        st.markdown(f"- `{h.get('action','')}` {h.get('handler','')}：{h.get('content','')}  _{h.get('created_at','')[:16]}_")
            except ApiError:
                pass

            st.divider()
            # 操作按钮
            cols = st.columns([1, 1, 2])
            if t.get("status") == "pending":
                with cols[0]:
                    if st.button("领取", key=f"assign_{t['id']}", use_container_width=True):
                        try:
                            api_client.assign_ticket(t["id"])
                            st.success("已领取")
                            st.rerun()
                        except ApiError as e:
                            st.error(e.message)

            if t.get("status") == "processing":
                with cols[0]:
                    with st.popover("提交处理记录", use_container_width=True):
                        handle_content = st.text_area("处理内容", key=f"handle_text_{t['id']}", height=100)
                        if st.button("提交", key=f"handle_btn_{t['id']}"):
                            try:
                                api_client.handle_ticket(t["id"], handle_content)
                                st.success("已提交处理记录")
                                st.rerun()
                            except ApiError as e:
                                st.error(e.message)

                with cols[1]:
                    with st.popover("关闭工单", use_container_width=True):
                        solution = st.text_area("最终解决方案（关闭后可沉淀）", key=f"close_text_{t['id']}", height=100)
                        archive = st.checkbox("关闭后沉淀为知识（待管理员审核）", value=True, key=f"archive_{t['id']}")
                        if st.button("确认关闭", key=f"close_btn_{t['id']}"):
                            try:
                                api_client.close_ticket(t["id"], solution, archive)
                                st.success("工单已关闭" + ("，已提交知识沉淀" if archive else ""))
                                st.rerun()
                            except ApiError as e:
                                st.error(e.message)

            if t.get("status") == "closed":
                st.success(f"工单已于 {t.get('closed_at','')[:16]} 关闭")
