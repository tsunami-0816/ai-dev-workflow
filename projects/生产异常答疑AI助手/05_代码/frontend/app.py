"""生产异常答疑 AI 助手 · 前端主入口（Streamlit）。
运行：streamlit run app.py
"""
import streamlit as st

import api_client
from api_client import ApiError

st.set_page_config(page_title="生产异常答疑 AI 助手", page_icon="🏭", layout="wide")

# 初始化 session_state
if "token" not in st.session_state:
    st.session_state["token"] = ""
if "user" not in st.session_state:
    st.session_state["user"] = None


def sidebar_nav():
    """侧边栏：用户信息、导航、退出。"""
    user = st.session_state.get("user")
    with st.sidebar:
        st.markdown("### 🏭 生产异常答疑")
        if user:
            st.success(f"已登录：{user.get('display_name') or user.get('username')}")
            st.caption(f"角色：{user.get('role')}")
            st.divider()
            st.page_link("pages/1_问答.py", label="💬 异常问答", icon="💬")
            st.page_link("pages/2_工单.py", label="📋 工单中心", icon="📋")
            st.page_link("pages/3_通知.py", label="🔔 通知", icon="🔔")
            if user.get("role") == "admin":
                st.divider()
                st.caption("管理功能")
                st.page_link("pages/4_知识库.py", label="📚 知识库", icon="📚")
                st.page_link("pages/5_知识审核.py", label="✅ 知识审核", icon="✅")
                st.page_link("pages/6_评估.py", label="📊 效果评估", icon="📊")
                st.page_link("pages/7_用户管理.py", label="👥 用户管理", icon="👥")
            st.divider()
            if st.button("退出登录", use_container_width=True):
                st.session_state["token"] = ""
                st.session_state["user"] = None
                st.rerun()
        else:
            st.info("请先登录")


def login_page():
    """登录页。"""
    st.markdown("# 🏭 生产异常答疑 AI 助手")
    st.caption("RAG 知识库答疑 + 异常分级派单 + 知识沉淀")
    st.divider()

    # 后端连通性
    try:
        h = api_client.health()
        st.success(f"后端已连接：{h.get('app')}，模型提供方：{h.get('model_provider')}，知识库切片：{h.get('kb_chunks')}")
    except Exception:
        st.warning("后端未连接，请先启动后端：`uvicorn app.main:app --port 8000`")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 登录")
        with st.form("login_form"):
            username = st.text_input("用户名", value="employee")
            password = st.text_input("密码", type="password", value="employee123")
            submitted = st.form_submit_button("登录", use_container_width=True)
            if submitted:
                try:
                    data = api_client.login(username, password)
                    st.session_state["token"] = data["access_token"]
                    st.session_state["user"] = data["user"]
                    st.success("登录成功")
                    st.rerun()
                except ApiError as e:
                    st.error(f"登录失败：{e.message}")

        st.divider()
        st.caption("默认账号（首次登录后请改密）：")
        st.code("admin/admin123    管理员\nrepair/repair123  维修负责人\nprocess/process123 工艺负责人\nsafety/safety123  安全负责人\nemployee/employee123 一线员工")


def main():
    user = st.session_state.get("user")
    if not user:
        login_page()
        return
    sidebar_nav()
    # 首页欢迎
    st.markdown("# 👋 欢迎使用生产异常答疑 AI 助手")
    st.caption(f"当前用户：{user.get('display_name') or user.get('username')}（{user.get('role')}）")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.page_link("pages/1_问答.py", label="💬 异常问答", use_container_width=True)
        st.caption("自然语言提问，返回手册条款与操作步骤；复杂问题自动派单")
    with col2:
        st.page_link("pages/2_工单.py", label="📋 工单中心", use_container_width=True)
        st.caption("查看、领取、处理、关闭工单；关闭时可沉淀知识")
    with col3:
        st.page_link("pages/3_通知.py", label="🔔 通知", use_container_width=True)
        st.caption("新工单派单通知与状态变更通知")

    st.divider()
    st.markdown("### 使用流程")
    st.markdown(
        "1. **一线员工**在「异常问答」提问 → 简单问题直接得到带来源的答案；复杂/高风险问题自动派单\n"
        "2. **负责人**在「通知」收到提醒 → 在「工单中心」领取 → 处理 → 关闭（可勾选沉淀知识）\n"
        "3. **管理员**在「知识审核」审核沉淀内容 → 通过后自动入库，后续相似问题可直接命中\n"
        "4. **管理员**在「知识库」上传设备手册/生产规范（支持 PDF/Word，扫描件自动 OCR）"
    )


if __name__ == "__main__":
    main()
