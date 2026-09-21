"""
银行问答系统 - 主入口
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.api import api_router
from app.core.security import get_password_hash
from app.models.user import User
from app.database import async_session_factory
from sqlalchemy import select


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("=" * 50)
    print("银行问答系统启动中...")
    print("=" * 50)

    # 初始化数据库
    await init_db()
    print("数据库初始化完成")

    # 创建默认管理员账号
    await create_admin_user()
    print("管理员账号初始化完成")

    # 确保上传目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    print("上传目录初始化完成")

    print("=" * 50)
    print("系统启动完成！")
    print(f"API文档: http://localhost:8000/docs")
    print("=" * 50)

    yield

    # 关闭时
    print("系统关闭中...")


async def create_admin_user():
    """创建默认管理员账号"""
    async with async_session_factory() as db:
        # 检查管理员是否已存在
        result = await db.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            admin = User(
                username=settings.ADMIN_USERNAME,
                email="admin@bankkb.com",
                password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True
            )
            db.add(admin)
            await db.commit()
            print(f"创建管理员账号: {settings.ADMIN_USERNAME}")
        else:
            print(f"管理员账号已存在: {settings.ADMIN_USERNAME}")


# 创建FastAPI应用
app = FastAPI(
    title="银行问答系统",
    description="基于LangChain的银行问答系统",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理（脱敏：不向客户端泄露内部实现细节）。
    已知业务异常（HTTPException 子类）由 FastAPI 自带处理器返回原始 detail。
    """
    logger = logging.getLogger("bankkb")
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"}
    )


@app.get("/", tags=["健康检查"])
async def root():
    """健康检查"""
    return {
        "message": "银行问答系统",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
