"""
聊天相关数据模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ChatSessionCreate(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题")


class ChatSessionResponse(BaseModel):
    """会话响应"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ReferenceItem(BaseModel):
    """引用来源项"""
    content: str
    source: str
    page: Optional[str] = None
    score: Optional[float] = None


class ChatMessageCreate(BaseModel):
    """发送消息请求"""
    content: str = Field(..., min_length=1, max_length=4000, description="消息内容")


class ChatMessageResponse(BaseModel):
    """消息响应"""
    id: str
    role: str
    content: str
    references: List[ReferenceItem] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    stream: bool = Field(True, description="是否流式响应")
