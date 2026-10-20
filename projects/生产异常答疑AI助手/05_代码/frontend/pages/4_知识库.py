"""知识库管理（admin）：上传文档、列表、删除、重建索引。"""
import streamlit as st

import api_client
from api_client import ApiError
from ui_utils import require_admin, sidebar

st.set_page_config(page_title="知识库", page_icon="📚", layout="wide")
require_admin()
sidebar()

st.markdown("# 📚 知识库管理")
st.caption("上传设备手册/生产规范（PDF/Word），自动解析、切分、向量化；扫描件自动 OCR")

# 上传
with st.expander("📤 上传新文档", expanded=True):
    uploaded_file = st.file_uploader("选择 PDF 或 Word 文件", type=["pdf", "docx", "doc"])
    scenario = st.selectbox("适用场景（可选，用于检索过滤）", ["", "设备故障", "工艺异常", "安全规范", "其他"])
    if uploaded_file and st.button("开始上传并入库", type="primary"):
        with st.spinner("正在解析、切分、向量化...（扫描件 OCR 可能较慢）"):
            try:
                file_bytes = uploaded_file.getvalue()
                result = api_client.upload_document(file_bytes, uploaded_file.name, scenario)
                st.success(f"上传完成：{result.get('filename')}，状态：{result.get('status')}，文档ID：{result.get('document_id')}")
                if result.get("status") != "indexed":
                    st.warning("入库未完全成功，请查看后端日志")
                st.rerun()
            except ApiError as e:
                st.error(f"上传失败：{e.message}")

st.divider()

# 文档列表
st.markdown("### 已入库文档")
try:
    docs = api_client.list_documents()
except ApiError as e:
    st.error(e.message)
    docs = []

if not docs:
    st.info("知识库为空，请先上传文档")
else:
    for d in docs:
        status_label = {"indexed": "✅ 已入库", "parsing": "⏳ 解析中", "failed": "❌ 失败", "uploaded": "📤 已上传"}.get(d.get("status"), d.get("status"))
        with st.container(border=True):
            cols = st.columns([4, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{d.get('filename','')}**")
                st.caption(f"ID: {d.get('id')} ｜ 类型: {d.get('doc_type','')} ｜ 场景: {d.get('scenario','-')} ｜ 切片数: {d.get('chunk_count',0)} ｜ 上传者: {d.get('uploaded_by','')} ｜ {d.get('created_at','')[:16]}")
                if d.get("error_msg"):
                    st.error(f"错误：{d['error_msg']}")
            with cols[1]:
                st.markdown(status_label)
            with cols[2]:
                if st.button("重建索引", key=f"rebuild_{d['id']}", use_container_width=True):
                    try:
                        api_client.rebuild_document(d["id"])
                        st.success("索引已重建")
                        st.rerun()
                    except ApiError as e:
                        st.error(e.message)
            with cols[3]:
                if st.button("🗑 删除", key=f"del_{d['id']}", use_container_width=True):
                    try:
                        api_client.delete_document(d["id"])
                        st.success("已删除（含向量与原始文件）")
                        st.rerun()
                    except ApiError as e:
                        st.error(e.message)
            with cols[4]:
                st.empty()
