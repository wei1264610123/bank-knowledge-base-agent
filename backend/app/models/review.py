"""
管理员回答质量抽查（评判记录）模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from app.database import Base


class QualityReview(Base):
    """AI 回答质量评判表（管理员抽查，一条回答一条评判，可更新）"""
    __tablename__ = "quality_reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("chat_messages.id"), nullable=False, index=True, unique=True)
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)        # 1-5 分
    comment = Column(Text, nullable=True)           # 评判意见
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<QualityReview {self.rating}>"