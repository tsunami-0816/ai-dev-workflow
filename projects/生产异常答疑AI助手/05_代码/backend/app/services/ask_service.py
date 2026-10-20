"""问答编排服务：多轮上下文 → 异常分级 → 简单问题 RAG 答疑 / 复杂问题自动派单 → 落库+通知+查询日志。"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger, get_trace_id
from app.models import Feedback, QueryLog, User
from app.rag.chains import retrieve_and_generate
from app.rag.grading import grade_question
from app.schemas.chat import AskRequest, AskResponse
from app.services import conversation_service, knowledge_service, notification_service, ticket_service

logger = get_logger(__name__)


def ask(db: Session, user: User, req: AskRequest) -> AskResponse:
    trace_id = get_trace_id()

    # 1. 会话（多轮追问）
    if req.conversation_id:
        conv = conversation_service.get_conversation(db, req.conversation_id, user.id)
    else:
        conv = conversation_service.create_conversation(db, user.id, title=req.question[:20])

    # 2. 历史消息（用于 RAG 上下文）
    history = [
        {"role": m.role, "content": m.content}
        for m in conversation_service.list_messages(db, conv.id, user.id)
    ]

    # 3. 写用户消息
    conversation_service.add_message(db, conv.id, "user", req.question)

    # 4. 异常分级
    grading = grade_question(req.question)
    need_ticket = grading.need_ticket

    # 低置信兜底：置信度 < 阈值且模型说"简单"时，转派单（宁派单不硬答）
    if grading.confidence < settings.CONFIDENCE_THRESHOLD and not need_ticket:
        need_ticket = True
        grading.need_ticket = True
        grading.reason = (grading.reason + "；分级置信度低，转派单").strip("；")

    ticket_id = None
    if need_ticket:
        # 5A. 复杂/高风险：自动派单
        ticket = ticket_service.create_ticket(
            db,
            title=req.question[:30],
            question=req.question,
            route_type=grading.route_type,
            severity=grading.severity,
            created_by_user_id=user.id,
            assignee_role=grading.route_type,
            confidence=grading.confidence,
            llm_reason=grading.reason,
        )
        ticket_id = ticket.id
        notification_service.create_notifications_for_role(
            db,
            role=grading.route_type,
            title=f"新工单 {ticket.id}（{grading.severity}）",
            content=f"{req.question[:80]}\n理由：{grading.reason}",
            ref_id=ticket.id,
        )
        answer = (
            f"该问题已判定为需派单处理。\n"
            f"工单号：{ticket.id}\n"
            f"负责人类型：{grading.route_type}，等级：{grading.severity}\n"
            f"理由：{grading.reason}\n"
            f"已通知对应负责人，请在「工单」页查看处理进度。"
        )
        steps = grading.suggested_checks
        sources = []
        no_relevant = False
        retrieve_ms = generate_ms = 0
    else:
        # 5B. 简单问题：RAG 答疑
        answer, steps, sources, no_relevant, retrieve_ms, generate_ms = retrieve_and_generate(
            req.question, scenario=req.scenario, history=history
        )
        # 无相关内容也转派单（兜底）
        if no_relevant:
            # 修复-第6步冒烟：兜底工单原来只通知 admin，process/repair/safety 角色收不到。
            # 改为：LLM 先按语义猜 route_type（仍走它的分级结果），猜不出或置信度低时设为 admin；
            # 同时给所有负责人角色都发通知，确保任何角色登录都能看到。
            fallback_route = grading.route_type or "admin"
            if grading.confidence < 0.4 or fallback_route not in ("repair", "process", "safety", "admin"):
                fallback_route = "admin"

            ticket = ticket_service.create_ticket(
                db,
                title=req.question[:30],
                question=req.question,
                route_type=fallback_route,
                severity="P1",
                created_by_user_id=user.id,
                assignee_role=fallback_route,
                confidence=grading.confidence,
                llm_reason="知识库无相关内容，转派单",
            )
            ticket_id = ticket.id
            need_ticket = True

            # 给所有负责人角色发通知（admin/repair/process/safety），
            # 避免只有 admin 角色能看到「知识库无答案」类工单
            for role in ("admin", "repair", "process", "safety"):
                notification_service.create_notifications_for_role(
                    db,
                    role=role,
                    title=f"新工单 {ticket.id}（知识库无答案）",
                    content=f"知识库无相关内容：{req.question[:80]}",
                    ref_id=ticket.id,
                )
            answer = (
                f"未在知识库中找到相关内容，已自动转派工单。\n"
                f"工单号：{ticket.id}，负责人类型：admin\n"
                f"请在「工单」页查看处理进度。"
            )

    total_ms = retrieve_ms + generate_ms
    route_result = "ticket" if need_ticket else "answer"

    # 6. 写助手消息
    assistant_msg = conversation_service.add_message(
        db,
        conv.id,
        "assistant",
        answer,
        sources=[s.model_dump() for s in sources] if sources else None,
        route_result=route_result,
        ticket_id=ticket_id,
    )

    # 7. 写查询日志（用于评估与统计）
    db.add(
        QueryLog(
            trace_id=trace_id,
            user_id=user.id,
            conversation_id=conv.id,
            question=req.question,
            route_result=route_result,
            severity=grading.severity,
            confidence=grading.confidence,
            retrieve_ms=retrieve_ms,
            generate_ms=generate_ms,
            total_ms=total_ms,
            need_ticket=need_ticket,
            ticket_id=ticket_id,
        )
    )
    db.commit()

    return AskResponse(
        conversation_id=conv.id,
        message_id=assistant_msg.id,
        answer=answer,
        steps=steps,
        sources=sources,
        route_result=route_result,
        need_ticket=need_ticket,
        ticket_id=ticket_id,
        grading=grading,
        no_relevant=no_relevant,
        retrieve_ms=retrieve_ms,
        generate_ms=generate_ms,
        total_ms=total_ms,
        trace_id=trace_id,
    )


def save_feedback(db: Session, trace_id: str, vote: str, comment: str, question: str = "") -> None:
    db.add(Feedback(trace_id=trace_id, question=question, vote=vote, comment=comment))
    db.commit()


def close_with_archive(db: Session, ticket_id: str, user: User, solution: str, archive: bool) -> object:
    """关闭工单并可选沉淀知识。"""
    ticket = ticket_service.close_ticket(
        db, ticket_id, user.id, user.role, handler=user.username, solution=solution
    )
    if archive and solution:
        knowledge_service.create_archive_from_ticket(db, ticket_id, solution)
    return ticket
