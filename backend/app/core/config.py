from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[2] = backend/
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """应用配置类"""

    # ==================== 应用基础 ====================
    APP_NAME: str = "CoCoWork"
    APP_VERSION: str = "0.1.0"
    DEBUG_MODE: bool = True

    # ==================== 服务器 ====================
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = True

    # ==================== API ====================
    API_PREFIX: str = "/api/v1"

    # ==================== JWT ====================
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1800

    # ==================== 凭证加密 ====================
    ENCRYPTION_KEY: str = "change-me-in-production"

    # ==================== 内置管理员（seed 脚本用）====================
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "nuguri990717@gmail.com"
    ADMIN_PASSWORD: str = "020121"  # 留空则 seed 脚本跳过创建

    # ==================== Redis ====================
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ==================== PostgreSQL ====================
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "postgres"
    PG_PASSWORD: str = ""
    PG_DATABASE: str = "cocowork"
    PG_POOL_MIN_SIZE: int = 1
    PG_POOL_MAX_SIZE: int = 10

    @property
    def pg_url(self) -> str:
        return f"postgres://{self.PG_USER}:{self.PG_PASSWORD}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DATABASE}"

    # ==================== 存储后端 ====================
    STORAGE_BACKEND: str = "r2"  # r2 | local
    STORAGE_LOCAL_ROOT: str = "data/uploads"  # local 后端根目录（相对 backend/）
    STORAGE_MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 单文件上传上限，默认 50MB

    # ==================== 对象存储 (R2) ====================
    R2_ENDPOINT: str = ""  # 例: https://<AccountID>.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""  # 例: cocowork

    # ==================== Langfuse 可观测 ====================
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
