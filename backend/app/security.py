from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User, UserRole

password_hasher = PasswordHasher()


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 使用 Argon2id 生成不可逆密码哈希。
def hash_password(password: str) -> str:
    return password_hasher.hash(password)


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 安全校验密码并兼容损坏哈希的失败路径。
def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 生成短期签名会话令牌并只在 HttpOnly Cookie 中传递。
def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "role": user.role.value, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 从签名 Cookie 恢复当前有效用户，所有业务接口复用此服务端授权入口。
def get_current_user(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    try:
        payload = jwt.decode(access_token, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效") from exc
    user = db.scalar(select(User).where(User.id == user_id, User.active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 以依赖工厂在服务端强制角色权限，不依赖前端菜单隐藏。
def require_roles(*roles: UserRole):
    # CHANGE [2026-08-30 12:58 +08:00] [WH400]: 在每次请求解析当前用户后检查允许角色集合。
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行此操作")
        return user
    return checker
