"""
管理员API路由
"""
import io
import csv
from datetime import datetime, time, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, exists
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import ChatFeedback, QuestionRequest
from app.models.audit import AuditLog
from app.models.review import QualityReview
from app.schemas.auth import UserResponse, AdminPasswordReset
from app.schemas.feedback import QuestionRequestResponse, QuestionRequestUpdate
from app.schemas.audit import AuditLogResponse
from app.schemas.review import ReviewCreate
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


# ---------- 数据导出（P2） ----------


def _build_csv(headers: List[str], rows: list) -> str:
    """生成带 UTF-8 BOM 的 CSV 文本（Excel 打开中文不乱码）"""
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


def _parse_range(start: Optional[str], end: Optional[str]):
    """解析可选的起始/结束日期（YYYY-MM-DD），返回 (since, until)"""
    since = None
    until = None
    if start:
        since = datetime.fromisoformat(start)
    if end:
        until = datetime.fromisoformat(end).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
    return since, until


@router.get("/export", summary="导出CSV报表（P2）")
async def export_csv(
    export_type: str = Query(..., alias="type", description="导出类型: questions/audit/feedback"),
    start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """导出问答明细 / 审计日志 / 反馈记录为 CSV（银行留档用）"""
    since, until = _parse_range(start, end)

    def _filter(column):
        conds = []
        if since:
            conds.append(column >= since)
        if until:
            conds.append(column <= until)
        return conds

    if export_type == "questions":
        # 问答明细：用户提问 + 会话 + 用户
        stmt = (
            select(ChatMessage.content, ChatMessage.created_at, ChatSession.title, User.username)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .join(User, User.id == ChatSession.user_id)
            .where(ChatMessage.role == "user")
            .order_by(ChatMessage.created_at)
        )
        stmt = stmt.where(*_filter(ChatMessage.created_at))
        rows = [
            [uid, title or "", content.replace("\n", " "), created.strftime("%Y-%m-%d %H:%M:%S")]
            for content, created, title, uid in (await db.execute(stmt)).all()
        ]
        return StreamingResponse(
            iter([_build_csv(["用户名", "会话", "问题内容", "提问时间"], rows)]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="questions_export.csv"'},
        )

    if export_type == "audit":
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        stmt = stmt.where(*_filter(AuditLog.created_at))
        logs = (await db.execute(stmt)).scalars().all()
        rows = [
            [
                log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                log.username or "",
                log.action,
                log.detail or "",
                log.target_type or "",
                log.ip or "",
            ]
            for log in logs
        ]
        return StreamingResponse(
            iter([_build_csv(["时间", "用户", "操作", "详情", "对象类型", "IP"], rows)]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="audit_export.csv"'},
        )

    if export_type == "feedback":
        # 反馈记录：内容 + 评价 + 原因 + 意见 + 用户 + 时间
        stmt = (
            select(
                ChatFeedback.created_at,
                User.username,
                ChatMessage.content,
                ChatFeedback.rating,
                ChatFeedback.reason,
                ChatFeedback.comment,
            )
            .join(ChatMessage, ChatMessage.id == ChatFeedback.message_id)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .join(User, User.id == ChatSession.user_id)
            .order_by(ChatFeedback.created_at.desc())
        )
        stmt = stmt.where(*_filter(ChatFeedback.created_at))
        rows = [
            [
                created.strftime("%Y-%m-%d %H:%M:%S"),
                username or "",
                (content or "").replace("\n", " "),
                rating,
                reason or "",
                comment or "",
            ]
            for created, username, content, rating, reason, comment in (await db.execute(stmt)).all()
        ]
        return StreamingResponse(
            iter([_build_csv(["时间", "用户", "回答内容", "评价", "原因", "意见"], rows)]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="feedback_export.csv"'},
        )

    raise HTTPException(status_code=400, detail="type 必须是 questions/audit/feedback")


# ---------- 回答质量抽查（P3：#13） ----------


@router.get("/reviews", summary="AI回答质量抽查列表（P3）")
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    reviewed: Optional[str] = Query(None, description="reviewed/unreviewed，不传为全部"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """抽查列表：全部 AI 回答，未评判的排前面，附用户反馈与管理员评判"""
    reviewed_exists = exists().where(QualityReview.message_id == ChatMessage.id)

    base = (
        select(
            ChatMessage.id, ChatMessage.content, ChatMessage.created_at,
            ChatSession.title, User.username
        )
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .join(User, User.id == ChatSession.user_id)
        .where(ChatMessage.role == "assistant")
    )

    if reviewed == "reviewed":
        base = base.where(reviewed_exists)
    elif reviewed == "unreviewed":
        base = base.where(~reviewed_exists)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0

    rows = (
        await db.execute(
            base
            .order_by(reviewed_exists.desc(), ChatMessage.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = []
    for msg_id, content, created_at, title, username in rows:
        fb = (
            await db.execute(select(ChatFeedback).where(ChatFeedback.message_id == msg_id))
        ).scalar_one_or_none()
        rv = (
            await db.execute(select(QualityReview).where(QualityReview.message_id == msg_id))
        ).scalar_one_or_none()
        items.append({
            "message_id": msg_id,
            "content": content,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "",
            "session_title": title or "",
            "username": username or "",
            "feedback": {
                "rating": fb.rating,
                "reason": fb.reason,
                "comment": fb.comment,
            } if fb else None,
            "review": {
                "rating": rv.rating,
                "comment": rv.comment,
                "reviewed_at": rv.updated_at.strftime("%Y-%m-%d %H:%M:%S") if rv.updated_at else "",
            } if rv else None,
        })

    total_ai = (
        await db.execute(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.role == "assistant")
        )
    ).scalar()
    reviewed_total = (
        await db.execute(select(func.count()).select_from(QualityReview))
    ).scalar()
    avg_rating = await db.execute(select(func.avg(QualityReview.rating)))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "total_answers": total_ai or 0,
            "reviewed": reviewed_total or 0,
            "unreviewed": (total_ai or 0) - (reviewed_total or 0),
            "avg_rating": round(avg_rating.scalar() or 0, 1),
        },
        "items": items,
    }


@router.post("/reviews", summary="提交/更新回答质量评判（P3）")
async def submit_review(
    data: ReviewCreate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """对 AI 回答给出 1-5 分评判；重复提交等于更新（保留一条记录）"""
    msg = (
        await db.execute(select(ChatMessage).where(ChatMessage.id == data.message_id))
    ).scalar_one_or_none()
    if not msg or msg.role != "assistant":
        raise HTTPException(status_code=404, detail="回答不存在")

    review = (
        await db.execute(select(QualityReview).where(QualityReview.message_id == data.message_id))
    ).scalar_one_or_none()

    if review:
        review.rating = data.rating
        review.comment = data.comment
        review.reviewer_id = current_user.id
        db.add(review)
        action = "update_review"
    else:
        review = QualityReview(
            message_id=data.message_id,
            reviewer_id=current_user.id,
            rating=data.rating,
            comment=data.comment,
        )
        db.add(review)
        action = "review_answer"

    await log_audit(
        db,
        action=action,
        username=current_user.username,
        user_id=current_user.id,
        target_type="message",
        target_id=data.message_id,
        detail=f"rating={data.rating}",
        ip=get_client_ip(request),
    )
    return {"message": "评判已保存", "rating": data.rating}


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
