"""应用配置：从 .env 读取，集中管理所有可调参数。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ===== 模型提供方：local（默认，省钱/离线） / api（云端兜底） =====
    MODEL_PROVIDER: str = "local"
    LOCAL_BASE_URL: str = "http://127.0.0.1:11434/v1"
    LOCAL_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"
    API_BASE_URL: str = ""
    API_KEY: str = ""
    API_MODEL: str = "qwen-plus"

    # ===== Embedding =====
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    API_EMBEDDING_MODEL: str = "text-embedding-v3"

    # ===== 存储 =====（运行时数据统一放在项目根 runtime/，与源码分离）
    CHROMA_DIR: str = "../../runtime/chroma"
    DATABASE_URL: str = "sqlite:///../../runtime/app.db"
    UPLOAD_DIR: str = "../../runtime/uploads"

    # ===== 安全 =====
    JWT_SECRET: str = "change-me-in-local-please"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ===== 检索 / 分级 =====
    RETRIEVE_TOP_K: int = 8
    ENSEMBLE_TOP_K: int = 4
    SIMILARITY_THRESHOLD: float = 0.35
    # ACC-01 相关性守门：Chroma L2 距离上限（实测 2026-10-20：库内问题 top 距离 ≤0.762，库外 ≥0.915）
    MAX_VECTOR_DISTANCE: float = 0.85
    CONFIDENCE_THRESHOLD: float = 0.6
    RERANK_ENABLED: bool = False

    # ===== 应用 =====
    APP_NAME: str = "生产异常答疑 AI 助手"
    API_PREFIX: str = "/api"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
