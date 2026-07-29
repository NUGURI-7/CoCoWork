from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[2] = backend/
BASE_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = BASE_DIR / ".env"


def _under_base(p: str) -> Path:
    """把配置里的路径锚在 BASE_DIR 上，不随进程 cwd 漂移。

    绝对路径原样返回（部署时可以直接配一个挂载点），相对路径挂到后端根下。
    不这么做的后果实测过：dev server 从 backend/app 启动时，"data/sandbox"
    会解析成 backend/app/data/sandbox —— 换个启动方式，历史工作区就凭空消失。
    """
    path = Path(p)
    return (path if path.is_absolute() else BASE_DIR / path).resolve()


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

    # ==================== 文档解析（云端路）====================
    # 部署者的凭证，不是用户的：用户建库时只选「走哪个后端」，不必自己去百度开账号。
    # 留空 = baidu 后端在 UI 上不可选（本地 pdfplumber 那条路永远可用，零配置底线）
    BAIDU_DOCPARSE_API_KEY: str = ""
    BAIDU_DOCPARSE_SECRET_KEY: str = ""

    # ---------- 沙箱：与 driver 无关 ----------
    SANDBOX_DRIVER: str = "local"  # local（开发者，宿主机直跑）| docker（生产，容器隔离）
    SANDBOX_LOCAL_ROOT: str = "data/sandbox"  # local driver 的工作区根目录（相对 backend/，也可填绝对路径）
    SANDBOX_ARTIFACT_MAX_SIZE: int = 20 * 1024 * 1024  # 单个产物大小上限，默认 20MB

    # ---------- 沙箱：docker driver 的容器参数 ----------
    # 这几条就是「隔离」本身 —— 隔离是这串启动参数，不是 docker run 这三个字（决策 16）
    SANDBOX_IMAGE: str = "cocowork-sandbox:0.1"
    SANDBOX_DOCKER_HOST: str = ""  # 空=本机 docker.sock；ssh://cocowork-server=远程 daemon
    SANDBOX_NETWORK: str = "cocowork-sandbox"  # 专用网络：能出公网、连不到 PG / Redis（决策 17）
    SANDBOX_MEMORY_MB: int = 512  # 要覆盖「脚本内存 + tmpfs 里的文件」，不只是脚本峰值
    SANDBOX_CPUS: float = 1.0
    SANDBOX_PIDS_LIMIT: int = 128  # 防 fork 炸弹
    SANDBOX_SESSION_TTL: int = 900  # 容器最长存活秒数；超时由 sandboxd 反收割强制清理

    # ---------- sandboxd 进程 ----------
    SANDBOX_TOKEN: str = ""  # 内部鉴权令牌，必填 —— 留空则 sandboxd 拒绝启动
    SANDBOXD_HOST: str = "127.0.0.1"  # 绝不可对外：这个进程握着 docker.sock，等于整台机器
    SANDBOXD_PORT: int = 8100

    @property
    def storage_local_path(self) -> Path:
        """local 存储后端的根目录（绝对路径）。"""
        return _under_base(self.STORAGE_LOCAL_ROOT)

    @property
    def sandbox_local_path(self) -> Path:
        """沙箱工作区的根目录（绝对路径）。"""
        return _under_base(self.SANDBOX_LOCAL_ROOT)

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
