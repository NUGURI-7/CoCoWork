"""Document（知识库文档）相关 schema。

包含两类：
- 文档实体对外输出（`DocumentOut`，列表/详情用）
- 上传发起流程 schema（`UploadInitIn` / `UploadInitOut`），按存储后端分流：
  - R2 → `strategy="presign"`，前端把文件 PUT 到 `upload_url`
  - Local → `strategy="passthrough"`，前端把文件 POST 到 `upload_endpoint`
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

#: 允许上传的文件扩展名（小写，不带点）。v1 范围。
#: 不放 env：是产品/业务边界，不该让部署者随手放宽（解析能力跟不上会炸管线）。
ALLOWED_FILE_TYPES: frozenset[str] = frozenset({"md", "txt"})


class DocumentOut(BaseModel):
    """文档对外输出。列表 / 详情共用。"""

    id: UUID
    knowledge_base_id: UUID
    name: str
    file_type: str
    size: int
    char_length: int
    paragraph_count: int
    chunk_count: int
    status: str
    stage: str
    error_message: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchDocumentIn(BaseModel):
    """批量操作（删除 / 向量化）请求体：一组文档 id。"""

    document_ids: list[UUID] = Field(
        min_length=1, max_length=200, description="目标文档 id 列表",
    )


class BatchDeleteOut(BaseModel):
    """批量删除响应：实际删除的文档数。"""

    deleted: int = Field(description="实际删除的文档数")


class BatchProcessOut(BaseModel):
    """批量向量化响应：已触发 / 被跳过（状态不允许）的文档 id。"""

    triggered: list[UUID] = Field(description="已入队处理的文档 id")
    skipped: list[UUID] = Field(description="状态不允许、被跳过的文档 id")


class UploadInitIn(BaseModel):
    """发起上传请求。后端据此预校验（扩展名 / 大小）并建 pending document。

    `file_type` 由后端从 `name` 后缀解析（前端不用单独传），所以这里只要文件名和大小。
    """

    name: str = Field(min_length=1, max_length=255, description="文件名（含扩展名）")
    size: int = Field(ge=0, description="文件字节数（前端从 File.size 取）")


class UploadInitOut(BaseModel):
    """发起上传响应。前端按 `strategy` 字段分流：

    - `presign`：把文件 PUT 到 `upload_url`，带上 `headers` 里的字段；完事调
      `upload-complete` 通知后端。
    - `passthrough`：把文件 multipart POST 到 `upload_endpoint`，后端一步落盘。
    """

    strategy: Literal["presign", "passthrough"] = Field(description="上传策略")
    document_id: UUID = Field(description="后端预建的 pending document id")
    upload_url: str | None = Field(default=None, description="presign 时填：R2 直传 URL")
    upload_endpoint: str | None = Field(
        default=None, description="passthrough 时填：后端 multipart 接收端点",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="发上传请求时需带的 header（presign PUT 通常需要 Content-Type）",
    )
