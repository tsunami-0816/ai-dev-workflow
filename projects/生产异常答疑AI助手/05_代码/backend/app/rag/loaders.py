"""文档加载器：文字版 PDF/Word 优先，扫描件 PDF 走 OCR（P1，需系统级 Tesseract+poppler）。"""
import os
from typing import List

from langchain_core.documents import Document

from app.core.logging import get_logger

logger = get_logger(__name__)


def load_document(file_path: str, doc_id: int, doc_name: str, scenario: str = "") -> List[Document]:
    """加载一份文档，返回带元数据的 langchain Document 列表（未切分）。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _load_pdf(file_path, doc_id, doc_name, scenario)
    if ext in (".docx", ".doc"):
        return _load_docx(file_path, doc_id, doc_name, scenario)
    raise ValueError(f"不支持的文件类型: {ext}")


def _meta(doc_id: int, doc_name: str, scenario: str, page: int = None, section: str = "") -> dict:
    # 修复-第6步冒烟：Chroma 要求 metadata 值必须是 str/int/float/bool，None 会在 upsert 时报错。
    # 这里把 None 字段直接剔除，让上游 metadata 永远不含 None 值。
    raw = {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "scenario": scenario,
        "page": page,
        "section": section,
        "source_type": "手册",
    }
    return {k: v for k, v in raw.items() if v is not None and v != ""}


def _load_pdf(file_path: str, doc_id: int, doc_name: str, scenario: str) -> List[Document]:
    docs: List[Document] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                docs.append(
                    Document(page_content=text, metadata=_meta(doc_id, doc_name, scenario, page=i + 1))
                )
    except Exception as e:
        logger.warning("pypdf 解析失败 %s: %s", doc_name, e)

    # 文字提取过少，判定为扫描件，尝试 OCR
    total_chars = sum(len(d.page_content) for d in docs)
    if total_chars < 80:
        logger.info("文档 %s 文字提取过少(%d)，尝试 OCR", doc_name, total_chars)
        ocr_docs = _ocr_pdf(file_path, doc_id, doc_name, scenario)
        if ocr_docs:
            return ocr_docs
    if not docs:
        raise RuntimeError(
            "PDF 无法提取文字。若为扫描件，请安装 Tesseract(含 chi_sim 语言包) 与 poppler 后重试。"
        )
    return docs


def _ocr_pdf(file_path: str, doc_id: int, doc_name: str, scenario: str) -> List[Document]:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        logger.warning("OCR 依赖未安装（pytesseract/pdf2image），跳过扫描件识别")
        return []
    try:
        images = convert_from_path(file_path, dpi=200)
        docs: List[Document] = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            if text.strip():
                docs.append(
                    Document(page_content=text, metadata=_meta(doc_id, doc_name, scenario, page=i + 1))
                )
        logger.info("OCR 完成 %s，共 %d 页有文字", doc_name, len(docs))
        return docs
    except Exception as e:
        logger.error("OCR 失败 %s: %s", doc_name, e)
        return []


def _load_docx(file_path: str, doc_id: int, doc_name: str, scenario: str) -> List[Document]:
    import docx2txt

    text = docx2txt.process(file_path)
    if not text or not text.strip():
        raise RuntimeError("Word 文档无有效文本内容")
    # Word 无稳定页码，按空行粗分为若干段，保留 section 序号
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    docs: List[Document] = []
    for idx, para in enumerate(paragraphs):
        docs.append(
            Document(
                page_content=para,
                metadata=_meta(doc_id, doc_name, scenario, page=None, section=f"段{idx + 1}"),
            )
        )
    return docs
