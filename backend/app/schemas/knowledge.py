"""
知识库相关数据模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class CategoryCreate(BaseModel):
    """创建分类请求"""
    name: str = Field(..., min_length=1, max_length=100, description="分类名称")
    description: Optional[str] = Field(None, description="分类描述")


class CategoryResponse(BaseModel):
    """分类响应"""
    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    document_count: int = 0

    class Config:
        from_attributes = True


class DocumentChunkResponse(BaseModel):
    """文档分块响应"""
    id: str
    content: str
    chunk_index: int
    chunk_metadata: dict = {}

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """文档响应"""
    id: str
    filename: str
    file_type: Optional[str]
    file_size: Optional[int]
    status: str
    chunk_count: int
    category_id: Optional[str]
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentDetailResponse(DocumentResponse):
    """文档详情响应"""
    chunks: List[DocumentChunkResponse] = []


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    total: int
    items: List[DocumentResponse]
    page: int
    page_size: int
