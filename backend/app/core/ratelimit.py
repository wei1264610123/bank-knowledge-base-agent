"""
简单内存限流器 - 用于登录等敏感接口

说明: 基于进程内存的滑动窗口实现，适用于单实例部署。
若将来部署为多 worker / 多实例，需替换为 Redis 等共享存储。
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, status


class SlidingWindowRateLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_attempts: int = 5, window_seconds: float = 300.0, detail: str = "请求过于频繁，请稍后再试"):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.detail = detail
        self._hits: dict = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """记录一次访问；超过阈值时抛出 429"""
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            # 丢弃窗口外的历史记录
            while dq and now - dq[0] > self.window_seconds:
                dq.popleft()
            if len(dq) >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=self.detail,
                )
            dq.append(now)

    def reset(self, key: str) -> None:
        """登录成功后清除该 key 的计数"""
        with self._lock:
            self._hits.pop(key, None)


# 登录限流：同一用户名 5 次 / 5 分钟
login_rate_limiter = SlidingWindowRateLimiter(
    max_attempts=5,
    window_seconds=300,
    detail="登录尝试过于频繁，请稍后再试",
)

# 问答限流（P1）：同一用户 20 次 / 1 分钟，防止刷接口烧钱
chat_rate_limiter = SlidingWindowRateLimiter(
    max_attempts=20,
    window_seconds=60,
    detail="发送消息过于频繁，请稍后再试",
)
