"""知识审核（admin）：审核工单关闭时沉淀的知识，通过后向量化入库。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_admin, sidebar

st.set_page_config(page_title="知识审核", page_icon="✅", layout="wide")
require_admin()
sidebar()

st.markdown("# ✅ 知识审核")
st.caption("审核工单关闭时沉淀的知识；通过后自动向量化入库，后续相似问题可直接命中")

status_filter = st.selectbox("状态", ["pending", "approved", "rejected", "全部"], index=0)
status_param = None if status_filter == "全部" else status_filter

try:
    archives = api_client.list_archives(status=status_param)
except ApiError as e:
    st.error(e.message)
    archives = []

if not archives:
    st.info("暂无待审核知识")
else:
    for a in archives:
        status_label = {"pending": "⏳ 待审核", "approved": "✅ 已通过（已入库）", "rejected": "❌ 已拒绝"}.get(a.get("status"), a.get("status"))
        with st.container(border=True):
            st.markdown(f"**标准问题：** {a.get('standard_question','')}")
            st.markdown(f"**解决方案：** {a.get('solution','')}")
            st.caption(
                f"ID: {a.get('id')} ｜ 来源工单: {a.get('source_ticket_id','-')} ｜ "
                f"标签: {a.get('tags','')} ｜ 状态: {status_label} ｜ {a.get('created_at','')[:16]}"
            )
            if a.get("status") == "pending":
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✅ 通过并入库", key=f"approve_{a['id']}", type="primary", use_container_width=True):
                        try:
                            api_client.review_archive(a["id"], True)
                            st.success("已通过并向量化入库")
                            st.rerun()
                        except ApiError as e:
                            st.error(e.message)
                with col2:
                    with st.popover("❌ 拒绝", use_container_width=True):
                        reason = st.text_input("拒绝原因（可选）", key=f"reject_reason_{a['id']}")
                        if st.button("确认拒绝", key=f"reject_btn_{a['id']}"):
                            try:
                                api_client.review_archive(a["id"], False, reason)
                                st.success("已拒绝")
                                st.rerun()
                            except ApiError as e:
                                st.error(e.message)
