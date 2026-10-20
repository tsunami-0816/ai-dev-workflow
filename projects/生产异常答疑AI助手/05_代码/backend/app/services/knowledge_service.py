"""知识沉淀服务：工单关闭时归档、管理员审核、审核通过后向量化入库。"""
from typing import Optional

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ERR_NOT_FOUND
from app.core.logging import get_logger
from app.models import KnowledgeArchive, Ticket
from app.rag.vectorstore import get_vectorstore

logger = get_logger(__name__)


def create_archive_from_ticket(db: Session, ticket_id: str, solution: str) -> KnowledgeArchive:
    t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not t:
        raise AppError(ERR_NOT_FOUND, "工单不存在", http_status=404)
    key = t.question[:50]
    existing = db.query(KnowledgeArchive).filter(KnowledgeArchive.similarity_key == key).first()
    if existing:
        logger.info("相同问题已存在归档 #%s，跳过重复沉淀", existing.id)
        return existing
    archive = KnowledgeArchive(
        standard_question=t.question,
        solution=solution or t.question,
        scenario="",
        tags=t.route_type,
        source_ticket_id=ticket_id,
        source_doc="工单沉淀",
        status="pending",
        indexed=False,
        similarity_key=key,
    )
    db.add(archive)
    db.commit()
    db.refresh(archive)
    return archive


def list_archives(db: Session, status: Optional[str] = None) -> list[KnowledgeArchive]:
    q = db.query(KnowledgeArchive)
    if status:
        q = q.filter(KnowledgeArchive.status == status)
    return q.order_by(KnowledgeArchive.created_at.desc()).all()


def review_archive(db: Session, archive_id: int, approve: bool, reject_reason: str = "") -> KnowledgeArchive:
    a = db.query(KnowledgeArchive).filter(KnowledgeArchive.id == archive_id).first()
    if not a:
        raise AppError(ERR_NOT_FOUND, "归档不存在", http_status=404)
    if approve:
        a.status = "approved"
        if not a.indexed:
            doc = Document(
                page_content=f"问题：{a.standard_question}\n解决方案：{a.solution}",
                metadata={
                    "doc_id": -1,
                    "doc_name": a.source_doc or "知识沉淀",
                    "scenario": a.scenario,
                    "page": None,
                    "section": f"归档#{a.id}",
                    "source_type": "归档知识",
                },
            )
            try:
                vs = get_vectorstore()
                vs.add_documents([doc])
                a.indexed = True
                logger.info("归档 #%s 已向量化入库", a.id)
            except Exception as e:
                logger.error("归档向量化失败 #%s: %s", a.id, e)
    else:
        a.status = "rejected"
    db.commit()
    db.refresh(a)
    return a
