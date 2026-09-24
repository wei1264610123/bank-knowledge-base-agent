"""
反馈与未解答问题相关数据模型
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class ChatFeedbackCreate(BaseModel):
    """提交回答反馈请求"""
    message_id: str = Field(..., description="AI消息ID")
    rating: Literal["up", "down"] = Field(..., description="评价：up=有用 / down=没用")
    reason: Optional[str] = Field(None, max_length=50, description="原因分类")
    comment: Optional[str] = Field(None, max_length=500, description="补充意见")


class QuestionRequestCreate(BaseModel):
    """提交未解答问题请求"""
    content: str = Field(..., min_length=1, max_length=500, description="问题内容")


class QuestionRequestUpdate(BaseModel):
    """管理员处理未解答问题请求"""
    status: Optional[Literal["open", "solved", "ignored"]] = None
    note: Optional[str] = Field(None, max_length=500, description="处理备注")


class QuestionRequestResponse(BaseModel):
    """未解答问题响应"""
    id: str
    user_id: str
    username: Optional[str] = None
    content: str
    status: str
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True