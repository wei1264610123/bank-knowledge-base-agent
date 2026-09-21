"""
安全模块单元测试（纯逻辑，无数据库/网络依赖）
被测: app/core/security.py
"""
from datetime import timedelta

import pytest
from jose import jwt, JWTError

from app.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
)


def test_password_hash_roundtrip():
    """密码哈希：哈希后不再等于明文，校验通过/失败均符合预期"""
    hashed = get_password_hash("MyPass#123")
    assert hashed != "MyPass#123"
    assert verify_password("MyPass#123", hashed)
    assert not verify_password("WrongPass", hashed)


def test_password_hash_is_unique_per_call():
    """同一个密码两次哈希结果应不同（带随机盐）"""
    h1 = get_password_hash("MyPass#123")
    h2 = get_password_hash("MyPass#123")
    assert h1 != h2
    assert verify_password("MyPass#123", h1)
    assert verify_password("MyPass#123", h2)


def test_create_token_contains_sub_and_exp():
    """生成的 JWT 应包含 sub 与 exp"""
    token = create_access_token({"sub": "user-1"})
    payload = jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    assert payload["sub"] == "user-1"
    assert "exp" in payload


def test_expired_token_rejected():
    """已过期 token 无法解码"""
    expired = create_access_token({"sub": "user-1"}, expires_delta=timedelta(seconds=-10))
    with pytest.raises(JWTError):
        jwt.decode(expired, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def test_wrong_secret_rejected():
    """错误密钥解码应失败"""
    token = create_access_token({"sub": "user-1"})
    with pytest.raises(JWTError):
        jwt.decode(token, "wrong-secret", algorithms=[settings.JWT_ALGORITHM])