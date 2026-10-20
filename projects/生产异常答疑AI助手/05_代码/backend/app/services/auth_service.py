"""认证与用户服务。"""
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ERR_FORBIDDEN, ERR_PARAM, ERR_UNAUTHORIZED
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, UserCreate


def authenticate(db: Session, req: LoginRequest) -> tuple[str, User]:
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        raise AppError(ERR_UNAUTHORIZED, "用户名或密码错误", http_status=401)
    token = create_access_token(user.id, user.role)
    return token, user


def create_user(db: Session, req: UserCreate, creator_role: str) -> User:
    if creator_role != "admin":
        raise AppError(ERR_FORBIDDEN, "仅管理员可创建用户", http_status=403)
    if db.query(User).filter(User.username == req.username).first():
        raise AppError(ERR_PARAM, "用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name or req.username,
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.asc()).all()
