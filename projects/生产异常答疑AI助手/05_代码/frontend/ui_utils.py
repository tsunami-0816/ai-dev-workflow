"""前端通用 UI：登录守卫、侧边栏导航。"""
import streamlit as st


def require_login() -> None:
    """未登录则跳回首页。"""
    if not st.session_state.get("token") or not st.session_state.get("user"):
        st.switch_page("app.py")
        st.stop()


def require_admin() -> None:
    """仅管理员可访问。"""
    require_login()
    if st.session_state.get("user", {}).get("role") != "admin":
        st.error("仅管理员可访问此页面")
        st.stop()


def sidebar() -> None:
    """统一侧边栏：用户信息、导航、退出。"""
    user = st.session_state.get("user")
    with st.sidebar:
        st.markdown("### 🏭 生产异常答疑")
        if user:
            st.success(f"{user.get('display_name') or user.get('username')}")
            st.caption(f"角色：{user.get('role')}")
            st.divider()
            st.page_link("app.py", label="🏠 首页")
            st.page_link("pages/1_问答.py", label="💬 异常问答")
            st.page_link("pages/2_工单.py", label="📋 工单中心")
            st.page_link("pages/3_通知.py", label="🔔 通知")
            if user.get("role") == "admin":
                st.divider()
                st.caption("管理功能")
                st.page_link("pages/4_知识库.py", label="📚 知识库")
                st.page_link("pages/5_知识审核.py", label="✅ 知识审核")
                st.page_link("pages/6_评估.py", label="📊 效果评估")
                st.page_link("pages/7_用户管理.py", label="👥 用户管理")
            st.divider()
            if st.button("退出登录", use_container_width=True):
                st.session_state["token"] = ""
                st.session_state["user"] = None
                st.switch_page("app.py")
