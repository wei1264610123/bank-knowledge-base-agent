"""
P3b 功能测试：管理员回答质量抽查（评判提交/更新/列表/过滤/权限）
不触网。
"""
from sqlalchemy import select, delete

from app.database import async_session_factory
from app.models.chat import ChatMessage, ChatSession
from app.models.feedback import ChatFeedback, QuestionRequest
from app.models.audit import AuditLog
from app.models.review import QualityReview


async def _clear_chat_tables():
    """清空聊天相关表，避免历史测试数据污染全局统计（仅测试库安全）"""
    async with async_session_factory() as db:
        await db.execute(delete(ChatFeedback))
        await db.execute(delete(QualityReview))
        await db.execute(delete(ChatMessage))
        await db.execute(delete(QuestionRequest))
        await db.execute(delete(ChatSession))
        await db.execute(delete(AuditLog))
        await db.commit()


async def _mk_assistant_message(client, token) -> str:
    """创建一条 AI 回答（user 会话 + assistant 消息），返回 message_id"""
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/auth/me", headers=headers)
    user_id = me.json()["id"]

    async with async_session_factory() as db:
        session = ChatSession(user_id=user_id, title="抽查会话")
        db.add(session)
        await db.flush()
        db.add(ChatMessage(session_id=session.id, role="assistant", content="这是 AI 的回答内容", references=[]))
        await db.commit()
        return (
            await db.execute(
                select(ChatMessage).where(ChatMessage.session_id == session.id)
            )
        ).scalar_one().id


async def test_submit_review_and_list(client, user_token_factory, admin_token):
    """管理员提交评判后，列表出现该条且统计更新"""
    await _clear_chat_tables()
    token = await user_token_factory()
    uheaders = {"Authorization": f"Bearer {token}"}
    message_id = await _mk_assistant_message(client, token)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.post(
        "/api/admin/reviews",
        json={"message_id": message_id, "rating": 5, "comment": "回答准确，引用相关"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rating"] == 5

    lst = await client.get("/api/admin/reviews", headers=admin_headers)
    assert lst.status_code == 200, lst.text
    data = lst.json()
    assert data["stats"]["total_answers"] == 1
    assert data["stats"]["reviewed"] == 1
    assert data["stats"]["avg_rating"] == 5.0
    item = data["items"][0]
    assert item["message_id"] == message_id
    assert item["review"]["rating"] == 5
    assert item["review"]["comment"] == "回答准确，引用相关"
    assert item["username"]


async def test_review_update_keeps_single(client, user_token_factory, admin_token):
    """重复提交=更新，不产生第二条记录"""
    await _clear_chat_tables()
    token = await user_token_factory()
    message_id = await _mk_assistant_message(client, token)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        "/api/admin/reviews",
        json={"message_id": message_id, "rating": 4},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/admin/reviews",
        json={"message_id": message_id, "rating": 2, "comment": "漏了限额说明"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text

    lst = await client.get("/api/admin/reviews", headers=admin_headers)
    data = lst.json()
    assert data["stats"]["reviewed"] == 1
    assert data["items"][0]["review"]["rating"] == 2
    assert data["stats"]["avg_rating"] == 2.0


async def test_reviews_filter_reviewed_unreviewed(client, user_token_factory, admin_token):
    """reviewed / unreviewed 过滤正确"""
    await _clear_chat_tables()
    token = await user_token_factory()
    m1 = await _mk_assistant_message(client, token)
    m2 = await _mk_assistant_message(client, token)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        "/api/admin/reviews", json={"message_id": m1, "rating": 3}, headers=admin_headers
    )

    rev = await client.get("/api/admin/reviews", params={"reviewed": "reviewed"}, headers=admin_headers)
    assert rev.status_code == 200
    assert [i["message_id"] for i in rev.json()["items"]] == [m1]

    unreviewed = await client.get("/api/admin/reviews", params={"reviewed": "unreviewed"}, headers=admin_headers)
    assert [i["message_id"] for i in unreviewed.json()["items"]] == [m2]


async def test_review_invalid_rating(client, admin_token):
    """评分越界返回 422"""
    resp = await client.post(
        "/api/admin/reviews",
        json={"message_id": "x", "rating": 6},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


async def test_review_message_not_found(client, admin_token):
    """回答不存在返回 404"""
    resp = await client.post(
        "/api/admin/reviews",
        json={"message_id": "no-such-message", "rating": 4},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


async def test_review_requires_admin(client, user_token_factory):
    """普通用户不能提交评判"""
    token = await user_token_factory()
    message_id = await _mk_assistant_message(client, token)
    resp = await client.post(
        "/api/admin/reviews",
        json={"message_id": message_id, "rating": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403