"""
回答反馈与未解答问题收集模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from app.database import Base


class ChatFeedback(Base):
    """回答反馈表（👍/👎 + 原因 + 意见）"""
    __tablename__ = "chat_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("chat_messages.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(String(10), nullable=False)  # 'up' 或 'down'
    reason = Column(String(50), nullable=True)   # 原因分类
    comment = Column(Text, nullable=True)        # 补充意见
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatFeedback {self.rating}>"


class QuestionRequest(Base):
    """未解答问题收集表（用户没找到答案时提交的问题）"""
    __tablename__ = "question_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="open", index=True)  # open / solved / ignored
    note = Column(Text, nullable=True)  # 管理员处理备注
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<QuestionRequest {self.status}>"