"""异常问答页：多轮对话、来源展示、工单触发、反馈。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_login, sidebar

st.set_page_config(page_title="异常问答", page_icon="💬", layout="wide")
require_login()
sidebar()

st.markdown("# 💬 异常问答")
st.caption("输入生产异常问题，简单问题直接返回手册条款与步骤，复杂/高风险问题自动派单")

# 初始化会话状态
if "chat_conversation_id" not in st.session_state:
    st.session_state["chat_conversation_id"] = None
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

# 会话选择
with st.expander("会话管理", expanded=False):
    col1, col2 = st.columns([2, 1])
    with col1:
        try:
            convs = api_client.list_conversations()
            options = [("（新建会话）", None)] + [(c.get("title", "未命名"), c["id"]) for c in convs]
            idx = st.selectbox(
                "选择历史会话",
                range(len(options)),
                format_func=lambda i: options[i][0],
                index=0,
            )
            selected_id = options[idx][1]
            if selected_id != st.session_state["chat_conversation_id"]:
                st.session_state["chat_conversation_id"] = selected_id
                if selected_id:
                    msgs = api_client.list_messages(selected_id)
                    st.session_state["chat_messages"] = msgs
                else:
                    st.session_state["chat_messages"] = []
        except ApiError as e:
            st.error(e.message)
    with col2:
        if st.button("新建会话", use_container_width=True):
            st.session_state["chat_conversation_id"] = None
            st.session_state["chat_messages"] = []
            st.rerun()

st.divider()

# 显示历史消息（含反馈按钮——必须在这个循环里注册，不能放在单次 `if question:` 块内部。
# 否则点反馈按钮触发 rerun 后 question 变成 None，整个反馈渲染代码就跳没了，
# widget 状态丢失，对话界面空白。）
for idx, msg in enumerate(st.session_state["chat_messages"]):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            # 来源（答案为「未找到」类回复时不显示，避免来源与答案矛盾）
            if msg.get("sources") and "未在知识库中找到相关内容" not in msg.get("content", ""):
                with st.expander(f"📖 参考来源（{len(msg['sources'])}）"):
                    for s in msg["sources"]:
                        st.markdown(f"- **{s.get('doc_name','')}** {s.get('section','')} 第{s.get('page') or '?'}页")
                        st.caption(s.get("text", "")[:200])
            # 工单提醒
            if msg.get("route_result") == "ticket" and msg.get("ticket_id"):
                st.warning(f"⚠️ 已自动派单：{msg['ticket_id']}")
            # 反馈按钮（key 绑定消息位置，rerun 后仍能正常注册；同时调后端 API 写入反馈表）
            col1, col2 = st.columns([1, 1])
            tid = msg.get("trace_id", "")
            with col1:
                if st.button("👍 有用", key=f"up_msg_{idx}"):
                    try:
                        api_client.feedback(tid or "", "up")
                        st.success("感谢反馈")
                    except ApiError as e:
                        st.error(e.message)
            with col2:
                if st.button("👎 没用", key=f"down_msg_{idx}"):
                    try:
                        api_client.feedback(tid or "", "down")
                        st.success("感谢反馈，我们会持续改进")
                    except ApiError as e:
                        st.error(e.message)

# 聊天输入
question = st.chat_input("请输入异常问题，例如：CNC 机床报警 E023 主轴过载怎么办？")
if question:
    st.session_state["chat_messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("正在检索知识库并分析..."):
            try:
                resp = api_client.ask(
                    question,
                    conversation_id=st.session_state["chat_conversation_id"],
                )
            except ApiError as e:
                st.error(f"提问失败：{e.message}")
                st.stop()

        st.session_state["chat_conversation_id"] = resp["conversation_id"]
        st.markdown(resp["answer"])

        # 步骤
        if resp.get("steps"):
            st.markdown("**🔧 建议操作步骤：**")
            for i, step in enumerate(resp["steps"], 1):
                st.markdown(f"{i}. {step}")

        # 工单信息
        if resp.get("need_ticket") and resp.get("ticket_id"):
            st.warning(
                f"⚠️ 已自动派单：工单号 **{resp['ticket_id']}**，"
                f"负责人类型：{resp.get('grading',{}).get('route_type','')}，"
                f"等级：{resp.get('grading',{}).get('severity','')}"
            )
            st.page_link("pages/2_工单.py", label="→ 前往工单中心查看")

        # 来源（答案为「未找到」类回复时不显示，避免来源与答案矛盾）
        if resp.get("sources") and "未在知识库中找到相关内容" not in resp.get("answer", ""):
            with st.expander(f"📖 参考来源（{len(resp['sources'])}）"):
                for s in resp["sources"]:
                    st.markdown(f"- **{s.get('doc_name','')}** {s.get('section','')} 第{s.get('page','?')}页（{s.get('source_type','')}）")
                    st.caption(s.get("text", "")[:200])

        # 耗时与分级
        st.caption(
            f"耗时：检索 {resp.get('retrieve_ms',0)}ms + 生成 {resp.get('generate_ms',0)}ms = {resp.get('total_ms',0)}ms ｜ "
            f"路由：{resp.get('route_result','')} ｜ 置信度：{resp.get('grading',{}).get('confidence',0):.2f} ｜ "
            f"trace_id: {resp.get('trace_id','')}"
        )

        # 反馈按钮已移至上方「历史消息循环」中注册，rerun 后也保持稳定。
        # 本次渲染结束后无需再重复渲染。

    # 保存助手消息到历史（额外存 trace_id 供循环里反馈按钮调 API）
    st.session_state["chat_messages"].append(
        {
            "role": "assistant",
            "content": resp["answer"],
            "sources": resp.get("sources"),
            "route_result": resp.get("route_result"),
            "ticket_id": resp.get("ticket_id"),
            "trace_id": resp.get("trace_id", ""),
        }
    )
