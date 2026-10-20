"""全部 ORM 模型（SQLAlchemy 2.0 风格）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    # employee / repair / process / safety / admin
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), default="")  # pdf / word / scanned
    scenario: Mapped[str] = mapped_column(String(32), default="")  # 设备故障/工艺异常/安全规范
    storage_path: Mapped[str] = mapped_column(String(512), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    # uploaded / parsing / indexed / failed
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversation.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    route_result: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # answer / ticket
    ticket_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Ticket(Base):
    __tablename__ = "ticket"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # T20261020-0001
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # repair / process / safety / admin
    route_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(8), default="P1")  # P0 / P1 / P2
    # pending / processing / resolved / closed
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    llm_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    assignee_role: Mapped[str] = mapped_column(String(32), default="")
    assignee: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    handlings: Mapped[list["TicketHandling"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class TicketHandling(Base):
    __tablename__ = "ticket_handling"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(64), ForeignKey("ticket.id"), nullable=False, index=True)
    handler: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(32), default="")  # assign / handle / close
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    ticket: Mapped[Ticket] = relationship(back_populates="handlings")


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), default="ticket_assign")  # ticket_assign / ticket_status / system
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    ref_type: Mapped[str] = mapped_column(String(32), default="ticket")
    ref_id: Mapped[str] = mapped_column(String(64), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class KnowledgeArchive(Base):
    __tablename__ = "knowledge_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_question: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str] = mapped_column(String(32), default="")
    tags: Mapped[str] = mapped_column(String(255), default="")
    source_ticket_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_doc: Mapped[str] = mapped_column(String(255), default="")
    # pending / approved / rejected
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    similarity_key: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    vote: Mapped[str] = mapped_column(String(8), default="")  # up / down
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class QATestCase(Base):
    __tablename__ = "qa_test_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario: Mapped[str] = mapped_column(String(32), default="")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    standard_answer: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String(255), default="")
    expected_route: Mapped[str] = mapped_column(String(16), default="answer")  # answer / ticket
    severity: Mapped[str] = mapped_column(String(8), default="P1")


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    question: Mapped[str] = mapped_column(Text, default="")
    route_result: Mapped[str] = mapped_column(String(16), default="")
    severity: Mapped[str] = mapped_column(String(8), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    retrieve_ms: Mapped[int] = mapped_column(Integer, default=0)
    generate_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(64), default="")
    retrieved_docs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    need_ticket: Mapped[bool] = mapped_column(Boolean, default=False)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


__all__ = [
    "Base",
    "User",
    "Document",
    "Conversation",
    "Message",
    "Ticket",
    "TicketHandling",
    "Notification",
    "KnowledgeArchive",
    "Feedback",
    "QATestCase",
    "QueryLog",
]
