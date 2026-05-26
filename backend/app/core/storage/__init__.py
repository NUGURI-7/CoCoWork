"""存储抽象装配入口。

业务层只 `from app.core.storage import storage`，背后是 R2 还是 local 由
`STORAGE_BACKEND` 环境变量决定（r2 / local）。
"""

from app.core.config import settings
from app.core.storage.base import Storage
from app.core.storage.local import LocalStorage
from app.core.storage.r2 import R2Storage


def _build_storage() -> Storage:
    backend = settings.STORAGE_BACKEND
    if backend == "r2":
        return R2Storage()
    if backend == "local":
        return LocalStorage()
    raise ValueError(f"不支持的 STORAGE_BACKEND: {backend!r}（可选：r2 / local）")


#: 模块级单例。业务层用：`from app.core.storage import storage; await storage.save(...)`
storage: Storage = _build_storage()

__all__ = ["Storage", "storage"]
