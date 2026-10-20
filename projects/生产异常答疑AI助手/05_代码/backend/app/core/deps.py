"""FastAPI 依赖：数据库会话、当前用户、角色权限。"""
from typing import Generator

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ERR_FORBIDDEN, ERR_UNAUTHORIZED
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(ERR_UNAUTHORIZED, "未提供登录凭证", http_status=401)
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload:
        raise AppError(ERR_UNAUTHORIZED, "登录凭证无效或已过期", http_status=401)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise AppError(ERR_UNAUTHORIZED, "登录凭证无效", http_status=401)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise AppError(ERR_UNAUTHORIZED, "用户不存在或已停用", http_status=401)
    return user


def require_roles(*roles: str):
    """角色权限装饰器依赖：require_roles("admin","repair")。"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(ERR_FORBIDDEN, "无权限执行此操作", http_status=403)
        return user

    return checker
