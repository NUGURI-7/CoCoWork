"""对象存储抽象接口。

业务层只依赖本接口、不认具体后端（R2 / 本地盘），换后端只改 env、业务零改动。

约定：
- 所有方法异步——调用方一律 `await`；具体实现若用同步库（boto3 / 文件 IO），
  在实现里用 `asyncio.to_thread` 包装，不阻塞事件循环。
- `key` = 对象标识：R2/S3 后端 = object key；本地后端 = 相对 STORAGE_LOCAL_ROOT 的路径。
"""

from abc import ABC, abstractmethod
from typing import BinaryIO


class Storage(ABC):
    """存储后端抽象基类。

    分两类能力：
    - 字节存取（`save`/`read`/`delete`/`exists`）：所有后端都支持，后端经手字节时用。
    - 预签名直传/下载（`generate_upload_url`/`generate_download_url`）：仅对象存储后端
      支持（`supports_presigned=True`），让客户端绕开后端直接读写存储；本地盘不支持。
    """

    #: 是否支持预签名直传/下载（对象存储=True，本地盘=False）
    supports_presigned: bool = False

    @abstractmethod
    async def save(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> None:
        """流式保存对象。

        `fileobj` 是 file-like（如 FastAPI `UploadFile.file`），实现内部应分块读写，
        避免把整个文件读进内存——这是支持几十兆大文件的关键。
        已存在的 key 会被覆盖。
        """

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """读取对象全部内容。不存在抛 `FileNotFoundError`。"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除对象。不存在不报错（幂等）。"""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """对象是否存在。"""

    async def generate_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires: int = 300,
    ) -> str:
        """生成预签名上传 URL（前端直传，PUT 到此 URL）。

        默认抛 `NotImplementedError`；仅对象存储后端（`supports_presigned=True`）重写。
        """
        raise NotImplementedError(f"{type(self).__name__} 不支持预签名上传")

    async def generate_download_url(self, key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL（前端直接 GET，绕开后端出站流量）。

        默认抛 `NotImplementedError`；仅对象存储后端（`supports_presigned=True`）重写。
        """
        raise NotImplementedError(f"{type(self).__name__} 不支持预签名下载")
