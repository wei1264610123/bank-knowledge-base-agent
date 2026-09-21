"""
pytest 全局配置：独立测试数据库 + 常用 fixtures
注意: DATABASE_URL 环境变量必须在导入 app.* 之前设置。
"""
import os
import uuid

# 使用独立测试数据库，绝不触碰生产 bankkb.db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./tests/test_bankkb.db"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import init_db, async_session_factory
from app.main import app
from app.models.user import User
from app.core.security import get_password_hash

TEST_PASSWORD = "TestPass#123456"
ADMIN_USERNAME = "ut_admin"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_db():
    """初始化测试数据库并创建种子管理员账号（幂等）"""
    await init_db()
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
        if not result.scalar_one_or_none():
            admin = User(
                username=ADMIN_USERNAME,
                email="ut_admin@test.com",
                password_hash=get_password_hash(TEST_PASSWORD),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.commit()
    yield


@pytest_asyncio.fixture
async def client():
    """HTTP 客户端（ASGI in-memory，不占端口）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    """管理员 token"""
    return await _login(client, ADMIN_USERNAME, TEST_PASSWORD)


@pytest_asyncio.fixture
async def user_token_factory(client: AsyncClient):
    """注册并登录一个全新普通用户，返回其 token"""
    async def factory() -> str:
        username = f"ut_user_{uuid.uuid4().hex[:8]}"
        resp = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@test.com",
                "password": TEST_PASSWORD,
            },
        )
        assert resp.status_code in (200, 201), resp.text
        return await _login(client, username, TEST_PASSWORD)
    return factory
