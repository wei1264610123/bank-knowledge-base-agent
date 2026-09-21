"""
知识库管理API路由（管理员）
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.category import Category
from app.schemas.knowledge import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentChunkResponse,
    CategoryCreate,
    CategoryResponse
)
from app.core.security import get_current_admin_user
from app.core.exceptions import DocumentNotFoundException, FileUploadException
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse, summary="获取文档列表")
async def get_documents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category_id: Optional[str] = Query(None, description="分类ID"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文档列表（管理员）"""
    query = select(Document)
    count_query = select(Document)

    if category_id:
        query = query.where(Document.category_id == category_id)
        count_query = count_query.where(Document.category_id == category_id)

    # 获取总数
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())

    # 分页查询
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
    )
    documents = result.scalars().all()

    items = []
    for doc in documents:
        doc_data = DocumentResponse.model_validate(doc)
        # 获取分类名称
        if doc.category_id:
            cat_result = await db.execute(select(Category).where(Category.id == doc.category_id))
            category = cat_result.scalar_one_or_none()
            if category:
                doc_data.category_name = category.name
        items.append(doc_data)

    return DocumentListResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size
    )


@router.post("/documents", response_model=DocumentResponse, summary="上传文档")
async def upload_document(
    file: UploadFile = File(..., description="上传文件"),
    category_id: Optional[str] = Query(None, description="分类ID"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文档到知识库"""
    knowledge_service = KnowledgeService()

    # 上传并处理文档
    document = await knowledge_service.upload_document(
        file=file,
        category_id=category_id,
        created_by=current_user.id,
        db=db
    )

    doc_response = DocumentResponse.model_validate(document)
    if document.category_id:
        cat_result = await db.execute(select(Category).where(Category.id == document.category_id))
        category = cat_result.scalar_one_or_none()
        if category:
            doc_response.category_name = category.name

    return doc_response


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse, summary="获取文档详情")
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文档详情"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise DocumentNotFoundException(document_id)

    # 先用不含chunks的基础响应验证，避免Pydantic同步触发懒加载报MissingGreenlet
    base = DocumentResponse.model_validate(document)
    doc_response = DocumentDetailResponse(**base.model_dump())

    # 按chunk_index有序加载分块
    chunks_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    doc_response.chunks = [DocumentChunkResponse.model_validate(chunk) for chunk in chunks_result.scalars().all()]

    if document.category_id:
        cat_result = await db.execute(select(Category).where(Category.id == document.category_id))
        category = cat_result.scalar_one_or_none()
        if category:
            doc_response.category_name = category.name

    return doc_response


@router.delete("/documents/{document_id}", summary="删除文档")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除文档"""
    knowledge_service = KnowledgeService()
    await knowledge_service.delete_document(document_id, db)
    return {"message": "文档已删除"}


@router.post("/documents/{document_id}/reprocess", response_model=DocumentResponse, summary="重新处理文档")
async def reprocess_document(
    document_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """重新处理文档（重新向量化）"""
    knowledge_service = KnowledgeService()
    document = await knowledge_service.reprocess_document(document_id, db)
    return DocumentResponse.model_validate(document)


@router.get("/categories", response_model=List[CategoryResponse], summary="获取分类列表")
async def get_categories(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取分类列表"""
    result = await db.execute(select(Category).order_by(Category.created_at.desc()))
    categories = result.scalars().all()

    response = []
    for cat in categories:
        cat_data = CategoryResponse.model_validate(cat)
        # 获取文档数量
        doc_count = await db.execute(
            select(Document).where(Document.category_id == cat.id)
        )
        cat_data.document_count = len(doc_count.scalars().all())
        response.append(cat_data)

    return response


@router.post("/categories", response_model=CategoryResponse, summary="创建分类")
async def create_category(
    category_data: CategoryCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新分类"""
    new_category = Category(
        name=category_data.name,
        description=category_data.description
    )
    db.add(new_category)
    await db.flush()

    return CategoryResponse.model_validate(new_category)


@router.delete("/categories/{category_id}", summary="删除分类")
async def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除分类"""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    # 检查分类下是否还有文档，避免产生悬空引用（外键约束已开启）
    doc_result = await db.execute(
        select(Document).where(Document.category_id == category_id).limit(1)
    )
    if doc_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该分类下仍有文档，请先移除或删除相关文档")

    await db.delete(category)
    return {"message": "分类已删除"}
