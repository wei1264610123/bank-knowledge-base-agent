"""
管理员API路由
"""
from datetime import datetime, time, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import ChatFeedback, QuestionRequest
from app.models.audit import AuditLog
from app.schemas.auth import UserResponse, AdminPasswordReset
from app.schemas.feedback import QuestionRequestResponse, QuestionRequestUpdate
from app.schemas.audit import AuditLogResponse
from app.core.security import get_current_admin_user, get_password_hash
from app.core.audit import log_audit, get_client_ip
from app.core.mask import mask_pii

router = APIRouter()


@router.get("/users", response_model=List[UserResponse], summary="获取用户列表")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表"""
    offset = (page - 1) * page_size
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = result.scalars().all()
    return [UserResponse.model_validate(user) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse, summary="获取用户详情")
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from app.core.exceptions import UserNotFoundException
        raise UserNotFoundException()
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/status", summary="更新用户状态")
async def update_user_status(
    user_id: str,
    request: Request,
    is_active: bool = Query(..., description="是否启用"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """启用/禁用用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from app.core.exceptions import UserNotFoundException
        raise UserNotFoundException()

    user.is_active = is_active
    db.add(user)

    # 审计：用户状态变更留痕（银行场景需记录管理员操作）
    await log_audit(
        db,
        action="update_user_status",
        username=current_user.username,
        user_id=current_user.id,
        target_type="user",
        target_id=user_id,
        detail=f"is_active={is_active}",
        ip=get_client_ip(request),
    )

    return {"message": f"用户已{'启用' if is_active else '禁用'}"}


@router.post("/users/{user_id}/reset-password", summary="管理员重置用户密码")
async def reset_user_password(
    user_id: str,
    payload: AdminPasswordReset,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员重置任意用户密码（忘记密码场景，无需邮件服务）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from app.core.exceptions import UserNotFoundException
        raise UserNotFoundException()

    user.password_hash = get_password_hash(payload.new_password)
    db.add(user)

    # 审计：管理员重置密码留痕（敏感操作必须可追溯）
    await log_audit(
        db,
        action="reset_password",
        username=current_user.username,
        user_id=current_user.id,
        target_type="user",
        target_id=user_id,
        detail=f"为 {user.username} 重置密码",
        ip=get_client_ip(request),
    )
    return {"message": f"已为用户 {user.username} 重置密码"}


@router.get("/dashboard", summary="获取运营数据面板")
async def get_dashboard(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """数据面板：问答量 / 反馈统计 / 热门问题 / 未命中榜（P1）"""
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    week_start = today_start - timedelta(days=6)

    async def count_questions(since=None):
        q = select(func.count(ChatMessage.id)).where(ChatMessage.role == "user")
        if since:
            q = q.where(ChatMessage.created_at >= since)
        return (await db.execute(q)).scalar() or 0

    today_questions = await count_questions(today_start)
    week_questions = await count_questions(week_start)
    total_questions = await count_questions()

    # 反馈统计
    up_count = (await db.execute(
        select(func.count(ChatFeedback.id)).where(ChatFeedback.rating == "up")
    )).scalar() or 0
    down_count = (await db.execute(
        select(func.count(ChatFeedback.id)).where(ChatFeedback.rating == "down")
    )).scalar() or 0

    # 热门问题 TOP10（按内容聚类统计，展示前脱敏：榜单可能含用户输入的手机号/身份证）
    hot_query = (
        select(ChatMessage.content, func.count(ChatMessage.id).label("cnt"))
        .where(ChatMessage.role == "user")
        .group_by(ChatMessage.content)
        .order_by(func.count(ChatMessage.id).desc())
        .limit(10)
    )
    hot_questions = [
        {"content": mask_pii(content), "count": cnt}
        for content, cnt in (await db.execute(hot_query)).all()
    ]

    # 未命中榜 TOP10（用户提交的未解答问题聚类，同样脱敏）
    unanswered_query = (
        select(QuestionRequest.content, func.count(QuestionRequest.id).label("cnt"))
        .group_by(QuestionRequest.content)
        .order_by(func.count(QuestionRequest.id).desc())
        .limit(10)
    )
    unanswered_top = [
        {"content": mask_pii(content), "count": cnt}
        for content, cnt in (await db.execute(unanswered_query)).all()
    ]

    return {
        "today_questions": today_questions,
        "week_questions": week_questions,
        "total_questions": total_questions,
        "up_feedback": up_count,
        "down_feedback": down_count,
        "hot_questions": hot_questions,
        "unanswered_top": unanswered_top,
    }


# ---------- 未解答问题收集管理 ----------

@router.get("/unanswered-requests", response_model=List[QuestionRequestResponse], summary="获取未解答问题列表")
async def list_unanswered_requests(
    status: Optional[str] = Query(None, description="按状态筛选: open/solved/ignored"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """查看用户提交的未解答问题（open 优先展示，方便优先处理）"""
    query = select(QuestionRequest).order_by(
        (QuestionRequest.status == "open").desc(),
        QuestionRequest.created_at.desc()
    )
    if status:
        query = query.where(QuestionRequest.status == status)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    requests = result.scalars().all()

    # 填充用户名（按 user_id 批量查询）
    user_ids = {req.user_id for req in requests}
    if user_ids:
        users_result = await db.execute(
            select(User.id, User.username).where(User.id.in_(user_ids))
        )
        username_map = {uid: uname for uid, uname in users_result.all()}
    else:
        username_map = {}

    response = []
    for req in requests:
        data = QuestionRequestResponse.model_validate(req)
        data.username = username_map.get(req.user_id)
        response.append(data)
    return response


@router.patch("/unanswered-requests/{request_id}", summary="处理未解答问题")
async def update_unanswered_request(
    request_id: str,
    payload: QuestionRequestUpdate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """标记问题已解决/忽略，并填写处理备注"""
    result = await db.execute(select(QuestionRequest).where(QuestionRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="问题记录不存在")

    if payload.status:
        req.status = payload.status
    if payload.note is not None:
        req.note = payload.note
    db.add(req)

    # 审计：问题处理留痕（知识补全闭环可追溯）
    await log_audit(
        db,
        action="handle_question",
        username=current_user.username,
        user_id=current_user.id,
        target_type="question_request",
        target_id=request_id,
        detail=f"status={req.status}" + (f", note={payload.note[:100]}" if payload.note else ""),
        ip=get_client_ip(request),
    )
    return {"message": "已更新"}


# ---------- 审计日志 ----------

@router.get("/audit-logs", response_model=List[AuditLogResponse], summary="获取审计日志")
async def get_audit_logs(
    action: Optional[str] = Query(None, description="按操作类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """查看审计日志（登录/上传/删除/反馈等敏感操作）"""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    return result.scalars().all()


@router.get("/stats", summary="获取统计数据")
async def get_stats(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取系统统计数据"""
    # 用户总数
    users_count = await db.execute(select(func.count(User.id)))
    total_users = users_count.scalar()

    # 文档总数
    docs_count = await db.execute(select(func.count(Document.id)))
    total_documents = docs_count.scalar()

    # 会话总数
    sessions_count = await db.execute(select(func.count(ChatSession.id)))
    total_sessions = sessions_count.scalar()

    # 消息总数
    messages_count = await db.execute(select(func.count(ChatMessage.id)))
    total_messages = messages_count.scalar()

    # 已处理文档数
    processed_docs = await db.execute(
        select(func.count(Document.id)).where(Document.status == "completed")
    )
    completed_documents = processed_docs.scalar()

    return {
        "total_users": total_users,
        "total_documents": total_documents,
        "completed_documents": completed_documents,
        "total_sessions": total_sessions,
        "total_messages": total_messages
    }
