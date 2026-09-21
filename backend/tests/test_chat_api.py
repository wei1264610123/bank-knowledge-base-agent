"""
聊天接口测试（会话 CRUD + 归属隔离 + Mock 后的流式问答）
被测: app/api/chat.py
注意: 全部通过 Mock 规避真实 LLM 调用，不消耗 API 额度。
"""


class FakeChatService:
    """Mock 的 ChatService：返回固定流式内容并模拟保存AI回复，不触网"""

    def __init__(self):
        pass

    async def stream_chat(self, message, history, session_id):
        yield "data: {\"type\": \"content\", \"content\": \"你好！\"}\n\n"
        yield "data: {\"type\": \"references\", \"references\": []}\n\n"
        # 模拟真实实现：用独立session把AI回复写入数据库
        from app.database import async_session_factory
        from app.models.chat import ChatMessage
        async with async_session_factory() as save_db:
            save_db.add(ChatMessage(session_id=session_id, role="assistant", content="你好！", references=[]))
            await save_db.commit()
        yield "data: {\"type\": \"done\"}\n\n"

    async def get_response(self, message, history, session_id):
        return {"content": "你好！", "references": []}


async def test_create_session(client, user_token_factory):
    """普通用户可创建会话"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/chat/sessions", json={"title": "我的会话"}, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["title"] == "我的会话"
    assert body["id"]


async def test_session_list_only_own(client, user_token_factory):
    """会话列表只返回当前用户的会话"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/chat/sessions", json={"title": "会话A"}, headers=headers)
    await client.post("/api/chat/sessions", json={"title": "会话B"}, headers=headers)

    resp = await client.get("/api/chat/sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


async def test_session_isolation(client, user_token_factory):
    """多用户数据隔离：B 看不到 A 的会话，也拿不到 A 会话的消息（安全关键）"""
    token_a = await user_token_factory()
    token_b = await user_token_factory()
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # A 建会话
    resp = await client.post("/api/chat/sessions", json={"title": "A的秘密"}, headers=headers_a)
    session_id = resp.json()["id"]

    # A 的列表有 1 个会话
    list_a = await client.get("/api/chat/sessions", headers=headers_a)
    assert len(list_a.json()) == 1

    # B 的列表为空
    list_b = await client.get("/api/chat/sessions", headers=headers_b)
    assert list_b.json() == []

    # B 直接访问 A 的会话消息 → 应被拒绝(404/403)
    msgs = await client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers_b)
    assert msgs.status_code in (403, 404)

    # B 直接删除 A 的会话 → 应被拒绝
    delete = await client.delete(f"/api/chat/sessions/{session_id}", headers=headers_b)
    assert delete.status_code in (403, 404)


async def test_delete_session(client, user_token_factory):
    """用户可删除自己的会话"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/chat/sessions", json={"title": "待删除"}, headers=headers)
    session_id = resp.json()["id"]

    delete = await client.delete(f"/api/chat/sessions/{session_id}", headers=headers)
    assert delete.status_code == 200, delete.text

    after = await client.get("/api/chat/sessions", headers=headers)
    assert after.json() == []


async def test_chat_stream_mocked(client, user_token_factory, mocker):
    """流式问答：ChatService 整体 Mock，验证 SSE 链路与消息保存"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/chat/sessions", json={"title": "压测会话"}, headers=headers)
    session_id = resp.json()["id"]

    mocker.patch("app.api.chat.ChatService", FakeChatService)

    resp = await client.post(
        "/api/chat/completions",
        headers=headers,
        json={"session_id": session_id, "message": "你好", "stream": True},
    )
    assert resp.status_code == 200, resp.text
    assert "你好" in resp.text
    assert "done" in resp.text

    # 消息历史应包含 user + assistant 两条
    history = await client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assert history.status_code == 200
    roles = [m["role"] for m in history.json()]
    assert roles == ["user", "assistant"]


async def test_chat_requires_auth(client):
    """未登录不能创建会话或发消息"""
    resp = await client.post("/api/chat/sessions", json={"title": "x"})
    assert resp.status_code == 401

    resp = await client.post(
        "/api/chat/completions",
        json={"session_id": "nope", "message": "hi", "stream": True},
    )
    assert resp.status_code == 401