"""工单路由：列表、详情、领取、处理、关闭（可选沉淀）、处理记录。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import PageResult
from app.schemas.ticket import CloseRequest, HandleRequest, TicketHandlingOut, TicketOut
from app.services import ask_service, ticket_service

router = APIRouter(prefix="/tickets", tags=["工单"])


@router.get("", response_model=PageResult[TicketOut])
def list_tickets(
    status: str | None = Query(None),
    route_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = ticket_service.list_tickets(
        db,
        user_id=user.id,
        role=user.role,
        status=status,
        route_type=route_type,
        page=page,
        page_size=page_size,
    )
    return PageResult(
        list=[TicketOut.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = ticket_service.get_ticket(db, ticket_id)
    ticket_service._check_role_access(t, user.id, user.role)
    return TicketOut.model_validate(t)


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = ticket_service.assign_ticket(db, ticket_id, user.id, user.role, user.username)
    return TicketOut.model_validate(t)


@router.post("/{ticket_id}/handle", response_model=TicketOut)
def handle(
    ticket_id: str,
    req: HandleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = ticket_service.handle_ticket(db, ticket_id, user.id, user.role, user.username, req.content)
    return TicketOut.model_validate(t)


@router.post("/{ticket_id}/close", response_model=TicketOut)
def close(
    ticket_id: str,
    req: CloseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = ask_service.close_with_archive(db, ticket_id, user, req.solution, req.archive)
    return TicketOut.model_validate(t)


@router.get("/{ticket_id}/handlings", response_model=list[TicketHandlingOut])
def handlings(ticket_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [TicketHandlingOut.model_validate(h) for h in ticket_service.list_handlings(db, ticket_id)]
