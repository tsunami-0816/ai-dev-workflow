"""工单服务：建单、列表（按角色可见性）、领取、处理、关闭、状态机。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ERR_FORBIDDEN, ERR_INVALID_TRANSITION, ERR_TICKET_NOT_FOUND
from app.core.logging import get_logger
from app.models import Ticket, TicketHandling

logger = get_logger(__name__)


def _gen_ticket_id(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"T{today}-"
    count = db.query(Ticket).filter(Ticket.id.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def create_ticket(
    db: Session,
    *,
    title: str,
    question: str,
    route_type: str,
    severity: str,
    created_by_user_id: int,
    assignee_role: str,
    confidence: float = 0.0,
    llm_reason: str = "",
    answer_snapshot: str = "",
) -> Ticket:
    ticket = Ticket(
        id=_gen_ticket_id(db),
        title=title or question[:30],
        question=question,
        route_type=route_type,
        severity=severity,
        status="pending",
        confidence=confidence,
        llm_reason=llm_reason,
        answer_snapshot=answer_snapshot,
        created_by_user_id=created_by_user_id,
        assignee_role=assignee_role,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def list_tickets(
    db: Session,
    *,
    user_id: int,
    role: str,
    status: Optional[str] = None,
    route_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Ticket], int]:
    q = db.query(Ticket)
    if role == "employee":
        q = q.filter(Ticket.created_by_user_id == user_id)
    elif role in ("repair", "process", "safety"):
        q = q.filter(or_(Ticket.assignee_role == role, Ticket.created_by_user_id == user_id))
    # admin 可见全部
    if status:
        q = q.filter(Ticket.status == status)
    if route_type:
        q = q.filter(Ticket.route_type == route_type)
    total = q.count()
    items = q.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_ticket(db: Session, ticket_id: str) -> Ticket:
    t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not t:
        raise AppError(ERR_TICKET_NOT_FOUND, "工单不存在", http_status=404)
    return t


def _check_role_access(ticket: Ticket, user_id: int, role: str) -> None:
    if role == "admin":
        return
    if role == "employee" and ticket.created_by_user_id != user_id:
        raise AppError(ERR_FORBIDDEN, "无权操作此工单", http_status=403)
    if role in ("repair", "process", "safety"):
        if ticket.assignee_role != role and ticket.created_by_user_id != user_id:
            raise AppError(ERR_FORBIDDEN, "无权操作此工单", http_status=403)


def assign_ticket(db: Session, ticket_id: str, user_id: int, role: str, assignee_name: str) -> Ticket:
    t = get_ticket(db, ticket_id)
    _check_role_access(t, user_id, role)
    if t.status != "pending":
        raise AppError(ERR_INVALID_TRANSITION, f"当前状态 {t.status} 不可领取")
    t.status = "processing"
    t.assignee = assignee_name
    db.add(TicketHandling(ticket_id=t.id, handler=assignee_name, action="assign", content="领取工单"))
    db.commit()
    db.refresh(t)
    return t


def handle_ticket(db: Session, ticket_id: str, user_id: int, role: str, handler: str, content: str) -> Ticket:
    t = get_ticket(db, ticket_id)
    _check_role_access(t, user_id, role)
    if t.status != "processing":
        raise AppError(ERR_INVALID_TRANSITION, "仅处理中的工单可提交处理结果")
    db.add(TicketHandling(ticket_id=t.id, handler=handler, action="handle", content=content))
    db.commit()
    db.refresh(t)
    return t


def close_ticket(
    db: Session, ticket_id: str, user_id: int, role: str, handler: str, solution: str = ""
) -> Ticket:
    t = get_ticket(db, ticket_id)
    _check_role_access(t, user_id, role)
    if t.status not in ("processing", "resolved"):
        raise AppError(ERR_INVALID_TRANSITION, f"当前状态 {t.status} 不可关闭")
    if solution:
        db.add(TicketHandling(ticket_id=t.id, handler=handler, action="close", content=solution))
    t.status = "closed"
    t.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t


def list_handlings(db: Session, ticket_id: str) -> list[TicketHandling]:
    return (
        db.query(TicketHandling)
        .filter(TicketHandling.ticket_id == ticket_id)
        .order_by(TicketHandling.id.asc())
        .all()
    )
