"""用户管理路由（仅 admin）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models import User
from app.schemas.auth import UserCreate, UserOut
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    return [UserOut.model_validate(u) for u in auth_service.list_users(db)]


@router.post("", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    u = auth_service.create_user(db, req, user.role)
    return UserOut.model_validate(u)
