"""
P3 功能测试：引用片段高亮数据支撑（document_id） + 文档原文预览接口
不触网：RAGService 用 __new__ 绕过 __init__（避免初始化 Embedding/Chroma）。
"""
import uuid

from langchain_core.documents import Document as LcDocument

from app.database import async_session_factory
from app.models.document import Document, DocumentChunk
from app.services.rag_service import RAGService


# ---------- 引用结构化（#10 高亮数据支撑） ----------


def test_format_references_has_document_id():
    """引用格式化应携带 document_id/chunk_index，供前端定位原文"""
    svc = RAGService.__new__(RAGService)
    docs = [
        LcDocument(page_content="片段A内容", metadata={"source": "产品手册.docx", "document_id": "d1", "chunk_index": 0}),
        LcDocument(page_content="片段B内容", metadata={"source": "产品手册.docx", "document_id": "d1", "chunk_index": 1}),
        LcDocument(page_content="片段C内容", metadata={"source": "制度.pdf", "document_id": "d2", "chunk_index": 0}),
    ]
    refs = svc.format_references(docs)

    # 同一来源去重为一条
    assert len(refs) == 2
    assert refs[0]["source"] == "产品手册.docx"
    assert refs[0]["document_id"] == "d1"
    assert refs[0]["chunk_index"] == 0
    assert refs[1]["document_id"] == "d2"
    assert refs[0]["content"] == "片段A内容"
    assert "score" in refs[0]


# ---------- 文档预览接口（#10） ----------


async def _create_doc(db, user_id, filename="产品介绍.docx"):
    doc = Document(
        filename=filename,
        file_path=f"uploads/{filename}",
        created_by=user_id,
        status="completed",
        chunk_count=2,
    )
    db.add(doc)
    await db.flush()
    db.add(DocumentChunk(document_id=doc.id, content="转账操作说明：登录手机银行后选择转账。", chunk_index=0))
    db.add(DocumentChunk(document_id=doc.id, content="贷款申请流程：提交资料后三个工作日审批。", chunk_index=1))
    await db.commit()
    return doc.id


async def test_preview_document_ok(client, user_token_factory):
    """普通登录用户可预览引用文档全文（按 chunk 顺序拼接）"""
    token = await user_token_factory()
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/auth/me", headers=headers)
    user_id = me.json()["id"]

    async with async_session_factory() as db:
        doc_id = await _create_doc(db, user_id)

    resp = await client.get(f"/api/chat/documents/{doc_id}/preview", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["filename"] == "产品介绍.docx"
    assert "转账操作说明" in data["content"]
    assert "贷款申请流程" in data["content"]
    # chunk 顺序：索引0 在前
    assert data["content"].index("转账操作说明") < data["content"].index("贷款申请流程")
    assert data["total_chunks"] == 2
    assert data["truncated"] is False


async def test_preview_document_not_found(client, user_token_factory):
    """文档不存在返回 404"""
    token = await user_token_factory()
    resp = await client.get(
        f"/api/chat/documents/{uuid.uuid4()}/preview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_preview_requires_login(client):
    """未登录访问预览接口返回 401"""
    resp = await client.get(f"/api/chat/documents/{uuid.uuid4()}/preview")
    assert resp.status_code in (401, 403), resp.text