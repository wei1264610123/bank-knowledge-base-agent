"""
认证API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    PasswordChange
)
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)
from app.core.exceptions import (
    UserAlreadyExistsException,
    UserNotFoundException,
    InvalidPasswordException
)
from app.core.ratelimit import login_rate_limiter
from app.core.audit import log_audit, get_client_ip

router = APIRouter()


@router.post("/register", response_model=UserResponse, summary="用户注册")
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise UserAlreadyExistsException(user_data.username)

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise UserAlreadyExistsException(f"邮箱 {user_data.email}")

    # 创建用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role="user"
    )
    db.add(new_user)
    await db.flush()

    # 审计：注册留痕
    await log_audit(
        db,
        action="register",
        username=new_user.username,
        user_id=new_user.id,
        ip=get_client_ip(request),
    )

    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    # 登录限流：防止暴力破解
    login_rate_limiter.check(form_data.username)

    # 查找用户
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        # 审计：登录失败留痕（含用户名与IP，供安全排查）
        await log_audit(
            db,
            action="login_failed",
            username=form_data.username,
            ip=get_client_ip(request),
        )
        raise InvalidPasswordException()

    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")

    # 登录成功，清除限流计数
    login_rate_limiter.reset(form_data.username)

    # 创建Token
    access_token = create_access_token(data={"sub": user.id})

    # 审计：登录成功留痕
    await log_audit(
        db,
        action="login",
        username=user.username,
        user_id=user.id,
        ip=get_client_ip(request),
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserResponse.model_validate(current_user)


@router.put("/password", summary="修改密码")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise InvalidPasswordException()

    # 更新密码
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.add(current_user)

    return {"message": "密码修改成功"}
