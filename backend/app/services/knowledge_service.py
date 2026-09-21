"""
知识库服务 - 文档处理与管理
"""
import os
import uuid
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.config import settings
from app.models.document import Document as DocumentModel, DocumentChunk
from app.services.rag_service import RAGService
from app.core.exceptions import DocumentNotFoundException, FileUploadException


class KnowledgeService:
    """知识库服务"""

    def __init__(self):
        self.rag_service = RAGService()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " "]
        )

    def _get_loader(self, file_path: str, file_type: str):
        """根据文件类型获取加载器"""
        if file_type == ".pdf":
            return PyPDFLoader(file_path)
        elif file_type == ".docx":
            return Docx2txtLoader(file_path)
        elif file_type in [".txt", ".md"]:
            return TextLoader(file_path, encoding="utf-8")
        else:
            raise FileUploadException(f"不支持的文件类型: {file_type}")

    async def upload_document(
        self,
        file: UploadFile,
        category_id: Optional[str],
        created_by: str,
        db: AsyncSession
    ) -> DocumentModel:
        """上传并处理文档"""
        # 验证文件类型
        file_type = os.path.splitext(file.filename)[1].lower()
        if file_type not in settings.ALLOWED_FILE_TYPES:
            raise FileUploadException(f"不支持的文件类型: {file_type}")

        # 验证文件大小
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise FileUploadException("文件大小超过限制")

        # 保存文件
        file_id = str(uuid.uuid4())
        file_name = f"{file_id}{file_type}"
        file_path = os.path.join(settings.UPLOAD_DIR, file_name)

        with open(file_path, "wb") as f:
            f.write(content)

        # 创建文档记录
        document = DocumentModel(
            filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            file_type=file_type,
            category_id=category_id,
            status="processing",
            created_by=created_by
        )
        db.add(document)
        await db.flush()

        try:
            # 处理文档
            await self._process_document(document, db)
            document.status = "completed"
        except Exception as e:
            document.status = "failed"
            print(f"文档处理失败: {e}")
            # 清理孤儿文件：处理失败时数据库记录会回滚，但磁盘文件需手动删除
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"已清理失败上传的孤儿文件: {file_path}")
            except OSError as cleanup_err:
                print(f"孤儿文件清理失败: {cleanup_err}")
            raise FileUploadException(f"文档处理失败: {str(e)}")

        return document

    async def _process_document(self, document: DocumentModel, db: AsyncSession):
        """处理文档（解析、分块、向量化）"""
        # 加载文档
        loader = self._get_loader(document.file_path, document.file_type)
        raw_docs = loader.load()

        # 分块
        chunks = self.text_splitter.split_documents(raw_docs)

        # 准备文档和ID
        doc_ids = [str(uuid.uuid4()) for _ in chunks]

        # 添加元数据
        for i, chunk in enumerate(chunks):
            chunk.metadata["source"] = document.filename
            chunk.metadata["document_id"] = document.id
            chunk.metadata["chunk_index"] = i

        # 添加到向量存储
        embedding_ids = await self.rag_service.add_documents(chunks, ids=doc_ids)

        # 保存分块记录
        for i, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=document.id,
                content=chunk.page_content,
                chunk_index=i,
                embedding_id=embedding_ids[i] if i < len(embedding_ids) else None,
                chunk_metadata=chunk.metadata
            )
            db.add(db_chunk)

        # 更新文档分块数量
        document.chunk_count = len(chunks)

    async def delete_document(self, document_id: str, db: AsyncSession):
        """删除文档"""
        # 查找文档
        result = await db.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            raise DocumentNotFoundException(document_id)

        # 删除向量存储中的数据
        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = chunks_result.scalars().all()

        if chunks:
            embedding_ids = [chunk.embedding_id for chunk in chunks if chunk.embedding_id]
            if embedding_ids:
                await self.rag_service.delete_documents(embedding_ids)

        # 删除文件
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        # 删除数据库记录
        await db.delete(document)

    async def reprocess_document(self, document_id: str, db: AsyncSession) -> DocumentModel:
        """重新处理文档（先处理新内容，成功后再替换旧数据，失败时旧数据仍可用）"""
        # 查找文档
        result = await db.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            raise DocumentNotFoundException(document_id)

        # 暂存旧分块（延迟到新内容成功后再删除）
        old_chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        old_chunks = old_chunks_result.scalars().all()

        document.status = "processing"
        document.chunk_count = 0

        try:
            # 第一步：处理并写入新内容（失败则回滚，旧数据不受影响）
            await self._process_document(document, db)
        except Exception as e:
            document.status = "failed"
            print(f"文档重新处理失败: {e}")
            raise

        # 第二步：新内容已成功入库，再删除旧分块与旧向量
        if old_chunks:
            embedding_ids = [chunk.embedding_id for chunk in old_chunks if chunk.embedding_id]
            if embedding_ids:
                await self.rag_service.delete_documents(embedding_ids)
            for chunk in old_chunks:
                await db.delete(chunk)

        document.status = "completed"
        return document
