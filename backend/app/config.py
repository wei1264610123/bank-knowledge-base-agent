"""
应用配置模块
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置"""
    
    # 数据库配置
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/bankkb.db"
    
    # JWT配置
    JWT_SECRET_KEY: str = "your-secret-key-please-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # 阿里云百炼（通义千问）
    DASHSCOPE_API_KEY: str = ""
    LLM_MODEL: str = "qwen-plus"
    OPENAI_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # 本地Embedding模型
    EMBEDDING_MODEL: str = "shibing624/text2vec-base-chinese"

    # 检索相关度过滤阈值（0 = 关闭）
    # 数值越小要求越严格；开启后相关性低于阈值的文档会被丢弃，导致"知识库无相关内容"兜底触发。
    # 需根据真实问答效果校准，默认关闭避免误伤。
    RETRIEVAL_RELEVANCE_THRESHOLD: float = 0.0
    
    # ChromaDB配置（本地文件存储）
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "chroma_data")
    CHROMA_COLLECTION: str = "bank_kb"
    
    # 文件上传配置
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    
    # 管理员默认账号
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "123456"
    
    # 支持的文件类型
    ALLOWED_FILE_TYPES: list = [".pdf", ".docx", ".txt", ".md", ".xlsx", ".pptx"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
