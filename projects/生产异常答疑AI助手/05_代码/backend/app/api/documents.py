"""知识库文档路由（上传/列表/删除/重建，仅 admin）。"""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models import User
from app.schemas.document import DocumentOut, UploadResponse
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["知识库文档"])


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    scenario: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    doc = await document_service.upload_document(db, file, scenario, user.username)
    msg = "文档已入库" if doc.status == "indexed" else f"入库状态：{doc.status}"
    return UploadResponse(document_id=doc.id, filename=doc.filename, status=doc.status, message=msg)


@router.get("", response_model=list[DocumentOut])
def list_docs(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    return [DocumentOut.model_validate(d) for d in document_service.list_documents(db)]


@router.delete("/{doc_id}")
def delete_doc(doc_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    document_service.delete_document(db, doc_id)
    return {"code": 0, "message": "文档已删除（含向量与原始文件）", "data": {"doc_id": doc_id}}


@router.post("/{doc_id}/rebuild", response_model=DocumentOut)
def rebuild(doc_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    doc = document_service.rebuild_document(db, doc_id)
    return DocumentOut.model_validate(doc)
