"""数据库会话：SessionLocal 与 FastAPI 依赖 get_db。"""
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from .engine import engine

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
