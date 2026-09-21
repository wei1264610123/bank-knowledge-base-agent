"""
管理员API路由
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from app.schemas.auth import UserResponse
from app.core.security import get_current_admin_user

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

    return {"message": f"用户已{'启用' if is_active else '禁用'}"}


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
