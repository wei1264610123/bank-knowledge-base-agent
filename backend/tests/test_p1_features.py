"""
P1 功能测试：信息脱敏 / 会话重命名 / 管理员重置密码 / 数据面板 / 问答限流
全部通过 Mock 规避真实 LLM 调用，不触网、不消耗 API 额度。
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.core.mask import mask_pii
from app.core.ratelimit import SlidingWindowRateLimiter
from app.database import async_session_factory
from app.models.chat import ChatMessage
from app.services.chat_service import ChatService

# ---------- 信息脱敏 ----------


def test_mask_phone():
    """手机号保留前3后4"""
    assert mask_pii("请联系13812345678办理") == "请联系138****5678办理"


def test_mask_id_card():
    """身份证保留前6后4（掩中间8位）"""
    assert mask_pii("身份证号110105199003071234") == "身份证号110105********1234"


def test_mask_bank_card():
    """银行卡保留前4后4"""
    assert mask_pii("6222021234567890123") == "6222********0123"


def test_mask_id_before_card():
    """18位身份证不能被银行卡规则误掩（顺序：先身份证）"""
    result = mask_pii("110105199003071234")
    assert "110105********1234" in result
    # 身份证掩码后中间为星号，不应再被误判成银行卡号
    assert "*" in result


def test_mask_idempotent():
    """脱敏幂等：对已脱敏文本再次处理结果不变"""
    text = "手机13812345678 身份证110105199003071234 卡6222021234567890123"
    once = mask_pii(text)
    twice = mask_pii(once)
    assert once == twice
    assert "1234567" not in once  # 手机号中段已掩


# ---------- 会话重命名 ----------


async def test_rename_session(client, user_token_factory):
    """用户可重命名自己的会话"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={"title": "旧标题"}, headers=headers)
    session_id = s.json()["id"]

    resp = await client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"title": "新标题"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "新标题"

    # 列表同步更新
    lst = await client.get("/api/chat/sessions", headers=headers)
    assert lst.json()[0]["title"] == "新标题"


async def test_rename_others_session_rejected(client, user_token_factory):
    """不能重命名他人会话"""
    token_a = await user_token_factory()
    token_b = await user_token_factory()
    s = await client.post("/api/chat/sessions", json={}, headers={"Authorization": f"Bearer {token_a}"})
    session_id = s.json()["id"]

    resp = await client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"title": "窃取改名"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code in (403, 404)


# ---------- 管理员重置密码（忘记密码场景） ----------


async def test_admin_reset_password(client, user_token_factory, admin_token):
    """管理员可重置普通用户密码，用户可用新密码登录"""
    token = await user_token_factory()
    # 获取该用户ID
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.post(
        f"/api/admin/users/{user_id}/reset-password",
        json={"new_password": "NewPass#999"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text

    # 用旧密码登录应失败，新密码可登录
    from conftest import TEST_PASSWORD
    old_login = await client.post(
        "/api/auth/login", data={"username": me.json()["username"], "password": TEST_PASSWORD}
    )
    assert old_login.status_code in (400, 401)
    new_login = await client.post(
        "/api/auth/login", data={"username": me.json()["username"], "password": "NewPass#999"}
    )
    assert new_login.status_code == 200, new_login.text


async def test_reset_password_requires_admin(client, user_token_factory):
    """普通用户不能调用管理员重置密码接口"""
    token = await user_token_factory()
    resp = await client.post(
        "/api/admin/users/whatever-id/reset-password",
        json={"new_password": "NewPass#999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---------- 数据面板 ----------


async def test_dashboard(client, user_token_factory, admin_token):
    """管理员可查看数据面板统计"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    # 制造 2 条用户消息 + 1 条 AI 消息 + 1 条反馈 + 1 条未解答问题
    await client.post("/api/chat/completions", json={"session_id": session_id, "message": "贷款利息多少？", "stream": False}, headers=headers)
    await client.post("/api/chat/completions", json={"session_id": session_id, "message": "贷款利息多少？", "stream": False}, headers=headers)
    async with async_session_factory() as db:
        db.add(ChatMessage(session_id=session_id, role="assistant", content="测试回复", references=[]))
        await db.commit()
    await client.post("/api/chat/unanswered-requests", json={"content": "信用卡年费是多少？"}, headers=headers)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.get("/api/admin/dashboard", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_questions"] >= 2
    assert "today_questions" in body and "week_questions" in body
    assert isinstance(body["hot_questions"], list)
    assert any(q["content"] == "贷款利息多少？" and q["count"] >= 2 for q in body["hot_questions"])
    assert any(q["content"] == "信用卡年费是多少？" for q in body["unanswered_top"])


# ---------- 问答限流 ----------


def test_rate_limiter_hits_limit():
    """滑动窗口限流器：超过阈值抛 429，窗口内可重试"""
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60, detail="测试限流")
    for _ in range(3):
        limiter.check("user_1")  # 前三次通过
    try:
        limiter.check("user_1")
        raise AssertionError("第4次应被拦截")
    except HTTPException as e:
        assert e.status_code == 429
        assert "测试限流" in e.detail


def test_rate_limiter_reset():
    """reset 后计数清零"""
    limiter = SlidingWindowRateLimiter(max_attempts=2, window_seconds=60)
    limiter.check("k")
    limiter.check("k")
    limiter.reset("k")
    limiter.check("k")  # reset 后可通过
    limiter.check("k")


# ---------- ChatService 输出脱敏（不触网） ----------


async def test_get_response_masks_pii(client, user_token_factory):
    """非流式：AI 回复与引用中的手机号被掩码（不调用真实 API）"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    s = await client.post("/api/chat/sessions", json={}, headers=headers)
    session_id = s.json()["id"]

    svc = ChatService.__new__(ChatService)
    svc.rag_service = MagicMock()
    svc.rag_service.retrieve_documents = AsyncMock(
        return_value=[MagicMock(page_content="客服电话请拨打13812345678", metadata={"source": "客服指南"})]
    )
    svc.rag_service.format_references = MagicMock(
        return_value=[{"content": "客服电话请拨打13812345678", "source": "客服指南"}]
    )
    svc._call_api = AsyncMock(return_value="请拨打客服电话13812345678咨询")

    result = await svc.get_response("客服电话多少？", [], session_id)
    assert "138****5678" in result["content"]
    assert "13812345678" not in result["content"]
    assert "138****5678" in result["references"][0]["content"]

    # 入库内容也是脱敏后的
    async with async_session_factory() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc())
        )).scalars().first()
        assert row.content == result["content"]
        assert "13812345678" not in row.content