"""Cloudflare R2（S3 兼容）存储实现。

- 碰网络的 `save/read/delete/exists`：同步 boto3 + `asyncio.to_thread` 包装，不阻塞事件循环。
- 预签名 `generate_upload_url/generate_download_url`：纯本地 HMAC 签名（不发网络请求），
  直接返回、不需要 `to_thread`。
"""

import asyncio
import logging
from functools import cached_property
from typing import TYPE_CHECKING, BinaryIO
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.storage.base import Storage

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = logging.getLogger(__name__)

# get_object 不存在报 NoSuchKey；head_object 不存在报 404（HEAD 无响应体）
_NOT_FOUND_CODES = {"NoSuchKey", "404"}


class R2Storage(Storage):
    """把对象存到 R2 的 Storage 实现。"""

    supports_presigned = True

    def __init__(self) -> None:
        self._bucket = settings.R2_BUCKET_NAME

    @cached_property
    def _client(self) -> "S3Client":
        # 懒加载：首次用到时才建 boto3 client，import/启动不依赖 R2 凭证；
        # 凭证缺失只在真调用时清晰报错（boto3 拒绝空 endpoint）。
        return boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",  # R2 固定 auto
            config=Config(signature_version="s3v4"),
        )

    async def save(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> None:
        # upload_fileobj 自动按需 multipart 分块上传大文件
        await asyncio.to_thread(
            self._client.upload_fileobj,
            fileobj,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    async def read(self, key: str) -> bytes:
        try:
            resp = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=key,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] in _NOT_FOUND_CODES:
                raise FileNotFoundError(f"对象不存在: {key}") from e
            raise
        return await asyncio.to_thread(resp["Body"].read)

    async def delete(self, key: str) -> None:
        # S3/R2 删不存在的 key 也返回成功，天然幂等
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key,
        )

    async def stat_size(self, key: str) -> int:
        try:
            resp = await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] in _NOT_FOUND_CODES:
                raise FileNotFoundError(f"对象不存在: {key}") from e
            raise
        return resp["ContentLength"]


    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] in _NOT_FOUND_CODES:
                return False
            raise
        return True

    async def generate_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires: int = 300,
    ) -> str:
        return self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )

    async def generate_download_url(
            self, key: str, expires: int = 3600, filename: str | None = None,
    ) -> str:
        params: dict = {"Bucket": self._bucket, "Key": key}
        if filename:
            # sanitize：去掉引号 + 控制字符，防 header 注入
            safe = filename.replace('"', "").replace("\r", "").replace("\n", "")
            # RFC 6266：filename= 兜底 ASCII，filename*= 支持 UTF-8（中文不乱码）
            encoded = quote(safe, safe="")
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{safe}"; filename*=UTF-8\'\'{encoded}'
            )
        return self._client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires,
        )
