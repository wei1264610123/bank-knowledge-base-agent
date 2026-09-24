"""
审计日志相关数据模型
"""
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: Optional[str] = None
    ip: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True