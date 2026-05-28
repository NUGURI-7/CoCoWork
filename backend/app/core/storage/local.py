"""本地文件系统存储实现。

主要用于开发（不联网、快）。文件落在 `STORAGE_LOCAL_ROOT` 下，`key` 作为相对路径。
同步文件 IO 用 `asyncio.to_thread` 包装，不阻塞事件循环。
"""

import asyncio
import shutil
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.storage.base import Storage


class LocalStorage(Storage):
    """把对象存到本地磁盘的 Storage 实现。

    本地盘没有"直传 URL"概念，故 `supports_presigned=False`，预签名方法继承基类默认
    （抛 NotImplementedError）；上传走后端中转。
    """

    supports_presigned = False

    def __init__(self) -> None:
        self._root = Path(settings.STORAGE_LOCAL_ROOT).resolve()

    def _resolve(self, key: str) -> Path:
        """key → 绝对路径，并防路径穿越（key 含 ../ 逃出 root 时拒绝）。"""
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"非法 key（路径穿越）: {key}")
        return path

    async def save(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> None:
        # 本地文件系统无 content_type 元数据，参数仅为接口统一而保留
        path = self._resolve(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as dst:
                shutil.copyfileobj(fileobj, dst)  # 分块拷贝，大文件不进内存

        await asyncio.to_thread(_write)

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"对象不存在: {key}")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return await asyncio.to_thread(path.is_file)

    async def stat_size(self, key: str) -> int:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"对象不存在: {key}")
        return await asyncio.to_thread(lambda : path.stat().st_size)
