"""知识沉淀路由：归档列表、管理员审核（通过后向量化入库）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models import User
from app.schemas.knowledge import ArchiveOut, ReviewRequest
from app.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["知识沉淀"])


@router.get("", response_model=list[ArchiveOut])
def list_archives(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return [ArchiveOut.model_validate(a) for a in knowledge_service.list_archives(db, status)]


@router.post("/{archive_id}/review", response_model=ArchiveOut)
def review(
    archive_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    a = knowledge_service.review_archive(db, archive_id, req.approve, req.reject_reason)
    return ArchiveOut.model_validate(a)
