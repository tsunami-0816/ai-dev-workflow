"""问答路由：多轮提问、反馈。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import User
from app.schemas.chat import AskRequest, AskResponse, FeedbackRequest
from app.services import ask_service

router = APIRouter(prefix="/chat", tags=["问答"])


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ask_service.ask(db, user, req)


@router.post("/feedback")
def feedback(req: FeedbackRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ask_service.save_feedback(db, req.trace_id, req.vote, req.comment)
    return {"code": 0, "message": "反馈已记录"}
