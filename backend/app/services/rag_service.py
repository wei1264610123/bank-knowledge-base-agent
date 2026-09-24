"""
RAG服务 - 向量检索核心实现（使用ChromaDB + 直接调用阿里云百炼Embedding API）
"""
from typing import List, Union
import httpx
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.config import settings


class DashScopeEmbeddings(Embeddings):
    """阿里云百炼Embedding（直接调用兼容接口）"""

    def __init__(self, api_key: str, model: str = "text-embedding-v1", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or settings.OPENAI_API_BASE
        # qwen3.7-text-embedding-flash 输出维度为1024
        self._dim = 1024

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """调用阿里云百炼Embedding API"""
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": texts
        }

        response = httpx.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            raise Exception(f"Embedding API错误: {response.status_code} - {response.text}")

        data = response.json()
        # 按索引排序返回向量
        data["data"].sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data["data"]]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档"""
        return self._call_api(texts)

    def embed_query(self, text: str) -> List[float]:
        """嵌入查询"""
        return self._call_api([text])[0]


class RAGService:
    """RAG检索服务"""

    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例（初始化失败时使用）"""
        cls._instance = None

    def __init__(self):
        # 确保初始化只执行成功一次
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._init_all()
        self._initialized = True
        print("RAG服务初始化完成")

    def _init_all(self):
        """执行完整初始化"""
        try:
            self.embeddings = self._init_embeddings()
            self.vector_store = self._init_vector_store()
        except Exception as e:
            print(f"RAG服务初始化失败: {e}")
            # 重置单例，允许下次调用重新初始化
            RAGService.reset_instance()
            raise

    def _init_embeddings(self) -> DashScopeEmbeddings:
        """初始化阿里云百炼Embedding模型"""
        print("正在初始化Embedding模型...")
        embeddings = DashScopeEmbeddings(
            api_key=settings.DASHSCOPE_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
        print("Embedding模型初始化完成")
        return embeddings

    def _init_vector_store(self) -> Chroma:
        """初始化ChromaDB向量存储"""
        print("正在初始化ChromaDB...")
        vector_store = Chroma(
            collection_name=settings.CHROMA_COLLECTION,
            embedding_function=self.embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR
        )
        print("ChromaDB初始化完成")
        return vector_store

    async def add_documents(self, documents: List[Document], ids: List[str] = None) -> List[str]:
        """添加文档到向量存储"""
        if not documents:
            return []

        print(f"正在添加 {len(documents)} 个文档片段...")
        added_ids = self.vector_store.add_documents(documents, ids=ids)
        print(f"成功添加 {len(added_ids)} 个文档片段到向量存储")
        return added_ids

    async def retrieve_documents(self, query: str, k: int = 5) -> List[Document]:
        """检索相关文档（支持相关度阈值过滤，阈值开启时低于阈值的文档会被丢弃）"""
        try:
            threshold = settings.RETRIEVAL_RELEVANCE_THRESHOLD or 0.0
            if threshold > 0:
                scored = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
                hits = [(doc, score) for doc, score in scored if score <= threshold]
                print(f"检索到 {len(hits)}/{len(scored)} 个相关文档（阈值 {threshold}）")
                return [doc for doc, _ in hits]
            docs = self.vector_store.similarity_search(query, k=k)
            print(f"检索到 {len(docs)} 个相关文档")
            return docs
        except Exception as e:
            print(f"文档检索失败: {e}")
            return []

    async def delete_documents(self, ids: List[str]) -> bool:
        """删除文档"""
        try:
            self.vector_store.delete(ids=ids)
            print(f"成功删除 {len(ids)} 个文档")
            return True
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False

    def format_references(self, docs: List[Document]) -> list:
        """格式化引用来源"""
        references = []
        seen_sources = set()

        for doc in docs:
            source = doc.metadata.get("source", "未知来源")
            # 避免重复引用
            if source not in seen_sources:
                references.append({
                    "content": doc.page_content[:300],
                    "source": source,
                    "page": doc.metadata.get("page", "N/A"),
                    "score": doc.metadata.get("score", 0)
                })
                seen_sources.add(source)

        return references