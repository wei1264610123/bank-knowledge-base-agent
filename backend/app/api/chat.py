"""
聊天API路由
"""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import get_db, async_session_factory
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import ChatFeedback, QuestionRequest
from app.models.document import Document, DocumentChunk
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRequest,
    SessionRename,
)
from app.schemas.feedback import ChatFeedbackCreate, QuestionRequestCreate
from app.core.security import get_current_user
from app.core.exceptions import SessionNotFoundException, DocumentNotFoundException
from app.core.audit import log_audit, get_client_ip
from app.core.ratelimit import chat_rate_limiter
from app.core.mask import mask_pii
from app.services.chat_service import ChatService

router = APIRouter()

# P3 文档预览：单次最多返回的纯文本字符数（防止超大文档拖垮前端）
MAX_PREVIEW_CHARS = 100_000


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

    # P1 脱敏：历史消息中的敏感信息掩码后返回（幂等，不污染数据库）
    responses = []
    for msg in messages:
        data = ChatMessageResponse.model_validate(msg)
        if data.role == "assistant":
            data.content = mask_pii(data.content)
        responses.append(data)
    return responses


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse, summary="重命名会话")
async def rename_session(
    session_id: str,
    payload: SessionRename,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重命名会话（P1）"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundException(session_id)

    old_title = session.title
    session.title = payload.title
    db.add(session)

    # 审计：会话重命名留痕
    await log_audit(
        db,
        action="rename_session",
        username=current_user.username,
        user_id=current_user.id,
        target_type="session",
        target_id=session_id,
        detail=f"{old_title[:30]} -> {payload.title[:30]}",
        ip=get_client_ip(request),
    )
    return ChatSessionResponse.model_validate(session)


@router.post("/completions", summary="发送消息")
async def chat_completion(
    chat_request: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """发送消息并获取AI回复。
    使用短生命周期session：验证会话、保存用户消息、取历史后立即释放连接，
    流式响应期间不占用数据库连接池（AI消息由ChatService用独立session保存）。
    """
    # P1 问答限流：同一用户 20 次/分钟，防止刷接口（按用户ID计数）
    chat_rate_limiter.check(str(current_user.id))

    # 注：聊天本身默认不记审计（量大）；如需合规全量留痕可在 ChatService 内补充。
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

        # P2 会话自动命名：默认标题"新对话"且为第一条提问时，用提问前20字生成标题
        if session.title == "新对话":
            auto_title = chat_request.message.strip().replace("\n", " ").replace("\r", " ")
            auto_title = auto_title[:20]
            if auto_title:
                session.title = auto_title
                db.add(session)
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


@router.get("/suggested-questions", summary="获取推荐问题（P2）")
async def get_suggested_questions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """智能推荐问题：热门提问 + 未解答的共性问题，最多6条，展示前脱敏"""
    # 热门问题：按内容聚类取前4
    hot_query = (
        select(ChatMessage.content, func.count(ChatMessage.id).label("cnt"))
        .where(ChatMessage.role == "user")
        .group_by(ChatMessage.content)
        .order_by(func.count(ChatMessage.id).desc())
        .limit(4)
    )
    popular = [mask_pii(c) for c, _ in (await db.execute(hot_query)).all()]

    # 未命中共性问题：open 状态按内容聚类取前4
    open_query = (
        select(QuestionRequest.content, func.count(QuestionRequest.id).label("cnt"))
        .where(QuestionRequest.status == "open")
        .group_by(QuestionRequest.content)
        .order_by(func.count(QuestionRequest.id).desc())
        .limit(4)
    )
    unanswered = [mask_pii(c) for c, _ in (await db.execute(open_query)).all()]

    questions = []
    for q in popular + unanswered:
        if q and q not in questions:
            questions.append(q)
        if len(questions) >= 6:
            break
    return questions


@router.get("/documents/{document_id}/preview", summary="文档原文预览（P3）")
async def preview_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """返回知识库文档解析后的全文（按分块顺序拼接），供聊天页引用预览/定位"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise DocumentNotFoundException(document_id)

    chunks = (
        await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    ).scalars().all()

    full_text = "\n\n".join(c.content for c in chunks).strip()
    truncated = False
    if len(full_text) > MAX_PREVIEW_CHARS:
        full_text = full_text[:MAX_PREVIEW_CHARS]
        truncated = True

    return {
        "document_id": document_id,
        "filename": document.filename,
        "content": full_text,
        "total_chunks": len(chunks),
        "truncated": truncated,
    }


@router.delete("/sessions/{session_id}/regenerate", summary="删除最后一条问答对（重新生成用）")
async def regenerate_clear_last(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除会话末尾的（用户问题 + AI回答）对，供前端"重新生成"使用。
    若 AI 回答已被用户评价（有反馈记录），拒绝删除以保留评价依据。"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise SessionNotFoundException(session_id)

    # 取最后两条消息
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(2)
    )
    last_two = list(result.scalars().all())

    to_delete = []
    if last_two and last_two[0].role == "assistant":
        # 检查该回答是否已被用户评价（评价后保留依据，不可重新生成）
        fb = await db.execute(
            select(ChatFeedback).where(ChatFeedback.message_id == last_two[0].id)
        )
        if fb.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="该回答已被评价，无法重新生成")
        to_delete.append(last_two[0])
        # 连带删除对应的上一条用户问题
        if len(last_two) == 2 and last_two[1].role == "user":
            to_delete.append(last_two[1])
    elif last_two and last_two[0].role == "user":
        # 最后一条是用户问题（AI 尚未回复），仅删该问题
        to_delete.append(last_two[0])
    else:
        raise HTTPException(status_code=400, detail="没有可删除的消息")

    for m in to_delete:
        await db.delete(m)

    # 审计：重新生成留痕
    await log_audit(
        db,
        action="regenerate_chat",
        username=current_user.username,
        user_id=current_user.id,
        target_type="session",
        target_id=session_id,
        ip=get_client_ip(request),
    )
    return {"message": "已删除最后一条问答"}


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
