"""数据库引擎：SQLite，支持多线程。"""
import os

from sqlalchemy import create_engine

from app.core.config import settings

# 确保 data 目录存在
_db_path = settings.DATABASE_URL.replace("sqlite:///", "")
if _db_path and not _db_path.startswith(":"):
    os.makedirs(os.path.dirname(os.path.abspath(_db_path)), exist_ok=True)

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,
)
