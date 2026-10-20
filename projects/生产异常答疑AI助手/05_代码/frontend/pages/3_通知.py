"""通知页：列表、未读数、标记已读。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_login, sidebar

st.set_page_config(page_title="通知", page_icon="🔔", layout="wide")
require_login()
sidebar()

st.markdown("# 🔔 通知")
st.caption("新工单派单通知与工单状态变更")

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    unread_only = st.checkbox("仅看未读", value=False)
with col2:
    if st.button("全部已读", use_container_width=True):
        try:
            api_client.mark_all_read()
            st.success("已全部标记为已读")
            st.rerun()
        except ApiError as e:
            st.error(e.message)
with col3:
    if st.button("🔄 刷新", use_container_width=True):
        st.rerun()

try:
    data = api_client.list_notifications(unread_only=unread_only)
    notifs = data.get("list", [])
    unread = data.get("unread_count", 0)
except ApiError as e:
    st.error(e.message)
    notifs = []
    unread = 0

st.metric("未读通知", unread)

if not notifs:
    st.info("暂无通知")
else:
    for n in notifs:
        icon = "🔔" if not n.get("is_read") else "✅"
        with st.container(border=True):
            cols = st.columns([6, 1])
            with cols[0]:
                st.markdown(f"{icon} **{n.get('title','')}**  _{n.get('created_at','')[:16]}_")
                st.markdown(n.get("content", ""))
                if n.get("ref_type") == "ticket" and n.get("ref_id"):
                    st.caption(f"关联工单：{n['ref_id']}")
            with cols[1]:
                if not n.get("is_read"):
                    if st.button("已读", key=f"read_{n['id']}", use_container_width=True):
                        try:
                            api_client.mark_read(n["id"])
                            st.rerun()
                        except ApiError as e:
                            st.error(e.message)
