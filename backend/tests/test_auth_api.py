"""
认证接口测试
被测: app/api/auth.py
"""
import uuid


def _random_username() -> str:
    return f"ut_register_{uuid.uuid4().hex[:8]}"


async def test_register_success(client):
    """注册成功返回用户信息，角色为普通用户"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": _random_username(),
            "email": f"u{uuid.uuid4().hex[:6]}@test.com",
            "password": "Pass#123456",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "id" in body


async def test_register_duplicate_username(client):
    """重复用户名注册应报错（400/409）"""
    username = _random_username()
    payload = {
        "username": username,
        "email": f"{username}@test.com",
        "password": "Pass#123456",
    }
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code in (200, 201), first.text

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409 or second.status_code >= 400
    assert "detail" in second.json()


async def test_register_invalid_email(client):
    """非法邮箱应返回 422"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": _random_username(),
            "email": "not-an-email",
            "password": "Pass#123456",
        },
    )
    assert resp.status_code == 422


async def test_login_success(client, user_token_factory):
    """正确账号密码登录返回 access_token 与用户信息"""
    token = await user_token_factory()
    assert isinstance(token, str) and len(token) > 20


async def test_login_wrong_password(client):
    """错误密码登录返回 400（业务契约：InvalidPasswordException 状态码为 400）"""
    username = _random_username()
    await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "Pass#123456",
        },
    )
    resp = await client.post(
        "/api/auth/login", data={"username": username, "password": "WrongPass#1"}
    )
    assert resp.status_code == 400
    assert "密码错误" in resp.json().get("detail", "")


async def test_me_without_token(client):
    """无 token 访问 /auth/me 返回 401"""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_with_valid_token(client, user_token_factory):
    """携带有效 token 访问 /auth/me 返回当前用户"""
    token = await user_token_factory()
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"].startswith("ut_user_")