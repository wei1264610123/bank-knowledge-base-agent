"""
审计日志模型（银行合规：登录/上传/删除/处理等敏感操作留痕）
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from app.database import Base


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(100), nullable=True)  # 冗余用户名，便于展示与留证
    action = Column(String(50), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)  # 对象类型: document/category/user/message...
    target_id = Column(String(100), nullable=True)
    detail = Column(Text, nullable=True)
    ip = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_action_created", "action", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action}>"