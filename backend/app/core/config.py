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

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
