"""
依赖注入模块
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.core.security import get_current_user, get_current_admin_user


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    """获取数据库会话"""
    return db


async def get_user(user: User = Depends(get_current_user)) -> User:
    """获取当前用户"""
    return user


async def get_admin_user(user: User = Depends(get_current_admin_user)) -> User:
    """获取管理员用户"""
    return user
