"""
管理员质量抽查相关 Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    """提交 / 更新回答质量评判"""
    message_id: str = Field(..., description="AI回答消息ID")
    rating: int = Field(..., ge=1, le=5, description="质量评分 1-5")
    comment: Optional[str] = Field(None, max_length=1000, description="评判意见")