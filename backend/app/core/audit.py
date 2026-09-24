"""
审计日志工具 - 敏感操作留痕（银行合规要求）

用法: 在需要审计的路由中调用 log_audit(db, ...)，
日志会随外层 session 在 commit 时一并写入 audit_logs 表。
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_audit(
    db: AsyncSession,
    action: str,
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    """记录一条审计日志（随外层 session 提交）"""
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip=ip,
    )
    db.add(entry)


def get_client_ip(request) -> Optional[str]:
    """提取客户端 IP（原样记录，不设默认值伪装）"""
    try:
        return request.client.host if request and request.client else None
    except Exception:
        return None