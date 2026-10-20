"""知识库文档服务：上传、解析（文字版+OCR）、切分、向量化、列表、删除、重建。"""
import os

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    ERR_FILE_TOO_LARGE,
    ERR_INTERNAL,
    ERR_NOT_FOUND,
    ERR_UNSUPPORTED_TYPE,
)
from app.core.logging import get_logger
from app.models import Document
from app.rag.loaders import load_document
from app.rag.splitter import split_documents
from app.rag.vectorstore import add_documents, delete_by_doc_id

logger = get_logger(__name__)

ALLOWED_EXT = {".pdf", ".docx", ".doc"}
MAX_SIZE = 50 * 1024 * 1024  # 50MB


async def upload_document(db: Session, file: UploadFile, scenario: str, uploaded_by: str) -> Document:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise AppError(ERR_UNSUPPORTED_TYPE, f"不支持的文件类型 {ext}，仅支持 PDF / Word")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise AppError(ERR_FILE_TOO_LARGE, "文件超过 50MB 限制")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    doc = Document(
        filename=file.filename or "unknown",
        doc_type=ext.lstrip("."),
        scenario=scenario,
        status="parsing",
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 修复 SEC-01：basename 净化文件名，防止 ../../ 路径穿越逃逸 uploads 目录
    safe_name = os.path.basename(file.filename or "unknown")
    storage_path = os.path.join(settings.UPLOAD_DIR, f"{doc.id}_{safe_name}")
    with open(storage_path, "wb") as f:
        f.write(content)
    doc.storage_path = storage_path

    try:
        raw_docs = load_document(storage_path, doc.id, doc.filename, scenario)
        chunks = split_documents(raw_docs)
        add_documents(chunks)
        doc.chunk_count = len(chunks)
        doc.status = "indexed"
        doc.error_msg = None
    except Exception as e:
        logger.error("文档入库失败 %s: %s", doc.filename, e)
        doc.status = "failed"
        doc.error_msg = str(e)[:500]

    db.commit()
    db.refresh(doc)
    return doc


def list_documents(db: Session) -> list[Document]:
    return db.query(Document).order_by(Document.id.desc()).all()


def get_document(db: Session, doc_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise AppError(ERR_NOT_FOUND, "文档不存在", http_status=404)
    return doc


def delete_document(db: Session, doc_id: int) -> None:
    doc = get_document(db, doc_id)
    try:
        delete_by_doc_id(doc_id)
    except Exception as e:
        logger.error("删除向量失败 doc_id=%s: %s", doc_id, e)
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception as e:
            logger.warning("删除原始文件失败: %s", e)
    db.delete(doc)
    db.commit()


def rebuild_document(db: Session, doc_id: int) -> Document:
    doc = get_document(db, doc_id)
    if not doc.storage_path or not os.path.exists(doc.storage_path):
        raise AppError(ERR_INTERNAL, "原始文件不存在，无法重建")
    delete_by_doc_id(doc_id)
    raw_docs = load_document(doc.storage_path, doc.id, doc.filename, doc.scenario)
    chunks = split_documents(raw_docs)
    add_documents(chunks)
    doc.chunk_count = len(chunks)
    doc.status = "indexed"
    doc.error_msg = None
    db.commit()
    db.refresh(doc)
    return doc
