"""
聊天API路由
"""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db, async_session_factory
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import ChatFeedback, QuestionRequest
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRequest
)
from app.schemas.feedback import ChatFeedbackCreate, QuestionRequestCreate
from app.core.security import get_current_user
from app.core.exceptions import SessionNotFoundException
from app.core.audit import log_audit, get_client_ip
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/sessions", response_model=List[ChatSessionResponse], summary="获取会话列表")
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的会话列表"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    response = []
    for session in sessions:
        # 获取消息数量
        msg_count = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session.id)
        )
        count = len(msg_count.scalars().all())
        session_data = ChatSessionResponse.model_validate(session)
        session_data.message_count = count
        response.append(session_data)

    return response


@router.post("/sessions", response_model=ChatSessionResponse, summary="创建新会话")
async def create_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新的聊天会话"""
    new_session = ChatSession(
        user_id=current_user.id,
        title=session_data.title or "新对话"
    )
    db.add(new_session)
    await db.flush()

    return ChatSessionResponse.model_validate(new_session)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse, summary="获取会话详情")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会话详情"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundException(session_id)

    return ChatSessionResponse.model_validate(session)


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除会话"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundException(session_id)

    await db.delete(session)
    # 审计：会话删除留痕
    await log_audit(
        db,
        action="delete_session",
        username=current_user.username,
        user_id=current_user.id,
        target_type="session",
        target_id=session_id,
        ip=get_client_ip(request),
    )
    return {"message": "会话已删除"}


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse], summary="获取消息历史")
async def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会话的消息历史"""
    # 验证会话属于当前用户
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundException(session_id)

    # 获取消息
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()

    return [ChatMessageResponse.model_validate(msg) for msg in messages]


@router.post("/completions", summary="发送消息")
async def chat_completion(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """发送消息并获取AI回复。
    使用短生命周期session：验证会话、保存用户消息、取历史后立即释放连接，
    流式响应期间不占用数据库连接池（AI消息由ChatService用独立session保存）。
    """
    async with async_session_factory() as db:
        # 验证会话属于当前用户
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.id == chat_request.session_id, ChatSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundException(chat_request.session_id)

        # 保存用户消息（立即提交，避免流式响应期间长期持有写锁阻塞其他请求）
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=chat_request.message
        )
        db.add(user_message)
        await db.flush()
        await db.commit()

        # 获取历史消息用于上下文
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
            .limit(20)  # 最近20条消息作为上下文
        )
        history = history_result.scalars().all()
    # 短生命周期session已在此释放连接

    # 创建ChatService并获取回复
    chat_service = ChatService()

    if chat_request.stream:
        # 流式响应
        return StreamingResponse(
            chat_service.stream_chat(
                message=chat_request.message,
                history=history,
                session_id=session.id
            ),
            media_type="text/event-stream"
        )
    else:
        # 非流式响应
        response = await chat_service.get_response(
            message=chat_request.message,
            history=history,
            session_id=session.id
        )
        return response


@router.post("/feedback", summary="提交回答反馈")
async def submit_feedback(
    feedback: ChatFeedbackCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交对AI回答的 👍/👎 反馈（只能评价自己会话中的AI消息）"""
    # 校验消息存在且属于当前用户
    result = await db.execute(
        select(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatMessage.id == feedback.message_id, ChatSession.user_id == current_user.id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在或无权评价")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="只能评价 AI 的回答")

    # 同一消息重复反馈则更新（upsert）
    existing_result = await db.execute(
        select(ChatFeedback).where(ChatFeedback.message_id == feedback.message_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        existing.rating = feedback.rating
        existing.reason = feedback.reason
        existing.comment = feedback.comment
    else:
        db.add(ChatFeedback(
            message_id=feedback.message_id,
            user_id=current_user.id,
            rating=feedback.rating,
            reason=feedback.reason,
            comment=feedback.comment
        ))

    # 审计：反馈留痕（含原因，便于质量分析）
    await log_audit(
        db,
        action="submit_feedback",
        username=current_user.username,
        user_id=current_user.id,
        target_type="message",
        target_id=feedback.message_id,
        detail=f"rating={feedback.rating}" + (f", reason={feedback.reason}" if feedback.reason else ""),
        ip=get_client_ip(request),
    )
    return {"message": "感谢您的反馈"}


@router.post("/unanswered-requests", summary="提交未解答问题")
async def submit_question_request(
    payload: QuestionRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """用户没找到答案时，提交问题给管理员补充知识库"""
    db.add(QuestionRequest(
        user_id=current_user.id,
        content=payload.content,
        status="open"
    ))
    # 审计：问题收集留痕
    await log_audit(
        db,
        action="submit_question",
        username=current_user.username,
        user_id=current_user.id,
        target_type="question_request",
        detail=payload.content[:100],
    )
    return {"message": "问题已提交，我们会尽快补充知识库，感谢反馈！"}
