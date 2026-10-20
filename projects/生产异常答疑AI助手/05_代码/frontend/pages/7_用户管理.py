"""用户管理（admin）：用户列表、创建用户。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_admin, sidebar

st.set_page_config(page_title="用户管理", page_icon="👥", layout="wide")
require_admin()
sidebar()

st.markdown("# 👥 用户管理")
st.caption("管理系统用户与角色权限")

# 创建用户
with st.expander("➕ 创建新用户", expanded=False):
    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("用户名 *")
            password = st.text_input("密码 *（至少6位）", type="password")
        with col2:
            display_name = st.text_input("显示名称")
            role = st.selectbox("角色 *", ["employee", "repair", "process", "safety", "admin"], format_func=lambda r: {
                "employee": "一线员工（提问）",
                "repair": "维修负责人",
                "process": "工艺负责人",
                "safety": "安全负责人",
                "admin": "管理员",
            }[r])
        submitted = st.form_submit_button("创建用户", type="primary")
        if submitted:
            if not username or not password:
                st.error("用户名和密码必填")
            else:
                try:
                    api_client.create_user(username, password, role, display_name)
                    st.success(f"用户 {username} 创建成功")
                    st.rerun()
                except ApiError as e:
                    st.error(f"创建失败：{e.message}")

st.divider()

# 用户列表
st.markdown("### 用户列表")
try:
    users = api_client.list_users()
except ApiError as e:
    st.error(e.message)
    users = []

if not users:
    st.info("暂无用户")
else:
    role_label = {
        "employee": "一线员工",
        "repair": "维修负责人",
        "process": "工艺负责人",
        "safety": "安全负责人",
        "admin": "管理员",
    }
    for u in users:
        status_icon = "✅" if u.get("is_active") else "🚫"
        with st.container(border=True):
            cols = st.columns([2, 2, 2, 1, 1])
            with cols[0]:
                st.markdown(f"**{u.get('username','')}**")
                st.caption(f"ID: {u.get('id')}")
            with cols[1]:
                st.markdown(u.get("display_name", ""))
            with cols[2]:
                st.markdown(f"角色：{role_label.get(u.get('role',''), u.get('role',''))}")
            with cols[3]:
                st.markdown(f"{status_icon} {'启用' if u.get('is_active') else '停用'}")
            with cols[4]:
                st.empty()
