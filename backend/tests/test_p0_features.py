"""
P0 功能测试：回答反馈 / 未解答问题收集 / 审计日志 / 知识库无内容兜底
被测: app/api/chat.py, app/api/admin.py, app/api/auth.py, app/services/chat_service.py
注意: ChatService 直接测试通过 __new__ 绕过 RAG 初始化，全程不触网、不调用 LLM。
"""

from unittest.mock import AsyncMock, MagicMock

from app.database import async_session_factory
from app.models.chat import ChatMessage
from app.models.feedback import ChatFeedback, QuestionRequest
from app.models.audit import AuditLog
from app.services.chat_service import ChatService

# ---------- 工具 ----------


async def _create_assistant_message(session_id: str, content: str = "测试回答") -> str:
    """直接在测试库插入一条 AI 消息，返回消息ID"""
    async with async_session_factory() as db:
        msg = ChatMessage(session_id=session_id, role="assistant", content=content, references=[])
        db.add(msg)
        await db.commit()
        return msg.id


def _build_service(no_docs: bool = True):
    """绕过 __init__ 构造 ChatService，避免触发 Chroma/Embedding 初始化"""
    svc = ChatService.__new__(ChatService)
    svc.rag_service = MagicMock()
    svc.rag_service.retrieve_documents = AsyncMock(return_value=[])
    svc.rag_service.format_references = MagicMock(return_value=[])
    return svc


# ---------- 回答反馈 ----------


async def test_feedback_success(client, user_token_factory):
    """用户可对会话内的 AI 回答提交 👍 反馈"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]
    msg_id = await _create_assistant_message(session_id)

    resp = await client.post(
        "/api/chat/feedback",
        json={"message_id": msg_id, "rating": "up", "reason": "helpful"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # 数据库中应存在反馈记录
    from sqlalchemy import select
    async with async_session_factory() as db:
        result = await db.execute(select(ChatFeedback).where(ChatFeedback.message_id == msg_id))
        fb = result.scalar_one_or_none()
        assert fb is not None
        assert fb.rating == "up"


async def test_feedback_reject_other_users_message(client, user_token_factory):
    """不能评价他人会话中的消息（数据隔离）"""
    token_a = await user_token_factory()
    token_b = await user_token_factory()
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    s = await client.post("/api/chat/sessions", json={}, headers=headers_a)
    session_id = s.json()["id"]
    msg_id = await _create_assistant_message(session_id, "他人回答")

    resp = await client.post(
        "/api/chat/feedback",
        json={"message_id": msg_id, "rating": "down"},
        headers=headers_b,
    )
    assert resp.status_code == 404


async def test_feedback_only_assistant(client, user_token_factory):
    """只能评价 AI 回答，不能评价用户自己的消息"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    async with async_session_factory() as db:
        user_msg = ChatMessage(session_id=session_id, role="user", content="我的问题", references=[])
        db.add(user_msg)
        await db.commit()
        user_msg_id = user_msg.id

    resp = await client.post(
        "/api/chat/feedback",
        json={"message_id": user_msg_id, "rating": "up"},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_feedback_duplicate_updates(client, user_token_factory):
    """重复反馈同一消息应更新而非报错（upsert）"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]
    msg_id = await _create_assistant_message(session_id)

    r1 = await client.post(
        "/api/chat/feedback", json={"message_id": msg_id, "rating": "down"}, headers=headers
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/chat/feedback", json={"message_id": msg_id, "rating": "up"}, headers=headers
    )
    assert r2.status_code == 200

    from sqlalchemy import select
    async with async_session_factory() as db:
        result = await db.execute(select(ChatFeedback).where(ChatFeedback.message_id == msg_id))
        fb = result.scalar_one()
        assert fb.rating == "up"  # 更新生效且仅一条记录


# ---------- 未解答问题收集 ----------


async def test_submit_question_request(client, user_token_factory):
    """用户可提交"没找到答案"的问题"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/chat/unanswered-requests",
        json={"content": "请问如何申请贷款额度提升？"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def test_admin_list_and_handle_question(client, user_token_factory, admin_token):
    """管理员可查看未解答问题并标记处理状态"""
    import uuid as _uuid
    question_content = f"如何开通网上银行业务？({_uuid.uuid4().hex[:6]})"

    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/chat/unanswered-requests",
        json={"content": question_content},
        headers=headers,
    )
    assert resp.status_code == 200

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    # 列表应包含 open 状态的问题
    lst = await client.get("/api/admin/unanswered-requests", headers=admin_headers)
    assert lst.status_code == 200, lst.text
    items = lst.json()
    assert len(items) >= 1
    target = next(i for i in items if i["content"] == question_content)
    assert target["status"] == "open"

    # 标记为已解决 + 备注
    patch = await client.patch(
        f"/api/admin/unanswered-requests/{target['id']}",
        json={"status": "solved", "note": "已补充对应文档"},
        headers=admin_headers,
    )
    assert patch.status_code == 200, patch.text

    lst2 = await client.get(
        "/api/admin/unanswered-requests", params={"status": "solved"}, headers=admin_headers
    )
    items2 = [i for i in lst2.json() if i["id"] == target["id"]]
    assert items2 and items2[0]["status"] == "solved"
    assert items2[0]["note"] == "已补充对应文档"

    async with async_session_factory() as db:
        row = await db.get(QuestionRequest, target["id"])
        assert row.status == "solved"


# ---------- 审计日志 ----------


async def test_audit_login_recorded(client, user_token_factory, admin_token):
    """登录成功应写入审计日志，管理员可查看并可按操作筛选"""
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 触发一次用户登录（写审计）
    await user_token_factory()

    logs = await client.get("/api/admin/audit-logs", headers=admin_headers)
    assert logs.status_code == 200, logs.text
    actions = [item["action"] for item in logs.json()]
    assert "login" in actions or "register" in actions

    # 按 action 筛选
    filtered = await client.get(
        "/api/admin/audit-logs", params={"action": "login"}, headers=admin_headers
    )
    assert filtered.status_code == 200
    assert all(item["action"] == "login" for item in filtered.json())

    async with async_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(select(AuditLog).where(AuditLog.action == "login").limit(1))
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.username  # 有操作者


# ---------- 知识库无内容兜底（核心 P0） ----------


async def test_stream_fallback_when_no_docs(client, user_token_factory):
    """检索无结果时：不调用 LLM，直接返回兜底文案并保存消息"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    svc = _build_service(no_docs=True)
    # 若兜底逻辑误调用 LLM，这里会抛错导致测试失败
    svc._call_api = MagicMock(side_effect=AssertionError("兜底分支不应调用 LLM"))

    import json as _json
    parsed = []
    async for chunk in svc.stream_chat("一个不存在于知识库的问题", [], session_id):
        parsed.append(_json.loads(chunk.split("data: ", 1)[-1].strip()))
    text = "".join(p["content"] for p in parsed if p["type"] == "content")

    assert "很抱歉" in text
    assert "没找到答案" in text
    assert any(p["type"] == "done" for p in parsed)

    # AI 消息已保存（内容为兜底文案）
    history = await client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    roles = [m["role"] for m in history.json()]
    assert "assistant" in roles
    last = history.json()[-1]
    assert "很抱歉" in last["content"]
    assert last["references"] == []


async def test_stream_fallback_done_carries_message_id(client, user_token_factory):
    """兜底回复的 done 事件应携带已保存消息的 ID（供反馈使用）"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    svc = _build_service(no_docs=True)
    done_id = None
    async for chunk in svc.stream_chat("完全没有的问题", [], session_id):
        if '"type": "done"' in chunk:
            import json as _json
            payload_title = chunk.split("data: ", 1)[-1].strip()
            done_id = _json.loads(payload_title).get("message_id")

    assert done_id, "done 事件应携带 message_id"
    assert isinstance(done_id, str) and len(done_id) > 10


async def test_stream_normal_done_carries_message_id(client, user_token_factory):
    """正常流式回复（有检索结果）done 也应携带已保存消息的 ID"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    svc = _build_service(no_docs=False)
    # 模拟检索到文档 + 模拟 LLM 流式输出
    svc.rag_service.retrieve_documents = AsyncMock(
        return_value=[MagicMock(page_content="银行定期存款利率如下", metadata={"source": "存款指南"})]
    )
    svc.rag_service.format_references = MagicMock(
        return_value=[{"content": "银行定期存款利率如下", "source": "存款指南"}]
    )

    async def fake_stream(messages):
        yield "定期存款利率为年化2.0%"

    svc._stream_api = fake_stream

    done_id = None
    async for chunk in svc.stream_chat("定期存款利率是多少", [], session_id):
        if '"type": "done"' in chunk:
            import json as _json
            payload = chunk.split("data: ", 1)[-1].strip()
            done_id = _json.loads(payload).get("message_id")

    assert done_id

    history = await client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assistant_msgs = [m for m in history.json() if m["role"] == "assistant"]
    assert assistant_msgs
    assert assistant_msgs[-1]["content"] == "定期存款利率为年化2.0%"


async def test_get_response_fallback(client, user_token_factory):
    """非流式接口在无检索结果时返回兜底文案 + message_id"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    svc = _build_service(no_docs=True)
    svc._call_api = MagicMock(side_effect=AssertionError("不应调用 LLM"))

    result = await svc.get_response("不存在的问题", [], session_id)
    assert result["content"] == svc.FALLBACK_REPLY
    assert result["references"] == []
    assert result["message_id"]