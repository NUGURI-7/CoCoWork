"""知识库文档：上传 / 列表 / 删除 / 下载链接路由。

URL nested 在 KB 下：`/knowledge-bases/{kb_id}/documents/...`。
上传按存储后端分流：
- R2 → presign 三段式（init / 前端 PUT R2 / complete）
- Local → 两步（init / passthrough 一步落盘）

正常情况前端按 init 返回的 `strategy` 字段决定调哪个；调错路径的请求被对应端点直接拒绝。
"""

from io import BytesIO
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.core.depends import get_current_user
from app.core.exceptions.types import ValidationException
from app.core.http import PageData, PaginationDep, ResponseModel, paginate, success
from app.core.storage import storage
from app.models.user import User
from app.schemas.knowledge import (
    BatchDeleteOut,
    BatchDocumentIn,
    BatchProcessOut,
    DocumentOut,
    UploadInitIn,
    UploadInitOut,
)
from app.services.knowledge import DocumentService, get_document_service
from app.services.knowledge.document_processor import process_document

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/documents",
    tags=["documents"],
)

CurrentUserDep = Annotated[User, Depends(get_current_user)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]

# 扩展名 → MIME 类型；白名单已限 md/txt，未知给兜底
_CONTENT_TYPE_BY_EXT = {
    "md": "text/markdown",
    "txt": "text/plain",
}


def _content_type_for(file_type: str) -> str:
    return _CONTENT_TYPE_BY_EXT.get(file_type, "application/octet-stream")


@router.post("/upload-init", summary="发起文件上传（按后端返不同策略）")
async def upload_init(
        kb_id: UUID,
        data: UploadInitIn,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[UploadInitOut]:
    """建 pending 文档记录，按存储后端返不同的上传策略。

    - R2 → presign 直传：前端 PUT 到 upload_url、带 headers 里的 Content-Type
    - Local → passthrough：前端 multipart POST 到 upload_endpoint
    """
    doc = await svc.create_pending(current_user, kb_id, data.name, data.size)
    content_type = _content_type_for(doc.file_type)

    if storage.supports_presigned:
        upload_url = await storage.generate_upload_url(
            doc.storage_key, content_type=content_type, expires=300,
        )
        out = UploadInitOut(
            strategy="presign",
            document_id=doc.id,
            upload_url=upload_url,
            headers={"Content-Type": content_type},
        )
    else:
        out = UploadInitOut(
            strategy="passthrough",
            document_id=doc.id,
            upload_endpoint=f"/knowledge-bases/{kb_id}/documents/{doc.id}/upload-passthrough",
        )

    return success(data=out, message="已建占位记录")


@router.post("/{doc_id}/upload-passthrough", summary="后端中转上传（仅 Local 后端）")
async def upload_passthrough(
        kb_id: UUID,
        doc_id: UUID,
        file: Annotated[UploadFile, File(description="文件字节流")],
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[None]:
    """Local 模式专用：multipart 接字节 → 落盘 → 标 uploaded。

    R2 模式应走 presign 直传 + upload-complete；此端点会直接拒绝。
    """
    if storage.supports_presigned:
        raise ValidationException(
            "当前存储后端不支持 passthrough 上传，请改走 presign 流程",
        )

    # 取 doc 做归属校验 + 拿 storage_key
    doc = await svc.get_by_id(current_user, kb_id, doc_id)
    content_type = _content_type_for(doc.file_type)

    # 字节流落盘（LocalStorage 内部用 shutil.copyfileobj 分块拷贝，不爆内存）
    await storage.save(doc.storage_key, file.file, content_type=content_type)

    # 复校真实大小 + 标 uploaded（超限会清干净 + 抛错）
    await svc.mark_uploaded(current_user, kb_id, doc_id)

    return success(message="上传完成")


@router.post("/{doc_id}/upload-complete", summary="确认上传完成（仅 R2 后端）")
async def upload_complete(
        kb_id: UUID,
        doc_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[None]:
    """R2 模式专用：前端 PUT 完 R2 后调；后端复校真实大小 + 标 uploaded。

    Local 模式应走 passthrough（一步完成）；此端点会直接拒绝。
    """
    if not storage.supports_presigned:
        raise ValidationException(
            "当前存储后端不支持 complete 流程，passthrough 已完成上传",
        )

    await svc.mark_uploaded(current_user, kb_id, doc_id)
    return success(message="上传已确认")


@router.post("/{doc_id}/process", summary="触发文档处理管线（向量化）")
async def process(
        kb_id: UUID,
        doc_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[DocumentOut]:
    """手动触发文档向量化：解析→切段→切块→embed。

        端点立即返回，处理在后台跑；前端轮询 `GET /{doc_id}` 看 status / stage 推进。
    """
    doc = await svc.trigger_progress(current_user, kb_id, doc_id)
    background_tasks.add_task(process_document, doc_id)
    return success(data=DocumentOut.model_validate(doc), message="已触发处理")


@router.post("/batch-process", summary="批量触发文档处理（向量化）")
async def batch_process(
        kb_id: UUID,
        data: BatchDocumentIn,
        background_tasks: BackgroundTasks,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[BatchProcessOut]:
    """批量向量化：service 过滤出可处理的 doc，路由层逐个入队后台任务。

    返回 triggered / skipped 两组 id，前端据此乐观更新 + 提示被跳过的。
    """
    triggered, skipped = await svc.trigger_progress_many(
        current_user, kb_id, data.document_ids,
    )
    for doc_id in triggered:
        background_tasks.add_task(process_document, doc_id)
    return success(
        data=BatchProcessOut(triggered=triggered, skipped=skipped),
        message=f"已触发 {len(triggered)} 个文档处理",
    )


@router.post("/batch-delete", summary="批量删除文档")
async def batch_delete(
        kb_id: UUID,
        data: BatchDocumentIn,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[BatchDeleteOut]:
    deleted = await svc.delete_many(current_user, kb_id, data.document_ids)
    return success(
        data=BatchDeleteOut(deleted=deleted),
        message=f"已删除 {deleted} 个文档",
    )


@router.get("", summary="列出知识库下的文档")
async def list_documents(
        kb_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[list[DocumentOut]]:
    docs = await svc.list_by_kb(current_user, kb_id)
    return success(data=[DocumentOut.model_validate(d) for d in docs])


@router.get("/page", summary="分页列出知识库下的文档")
async def list_documents_paginated(
        kb_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
        params: PaginationDep,
) -> ResponseModel[PageData[DocumentOut]]:
    qs = svc.query_by_kb(current_user, kb_id)
    return success(data=await paginate(qs, params, out=DocumentOut))


@router.get("/{doc_id}", summary="文档详情")
async def get_document(
        kb_id: UUID,
        doc_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[DocumentOut]:
    doc = await svc.get_by_id(current_user, kb_id, doc_id)
    return success(data=DocumentOut.model_validate(doc))


@router.delete("/{doc_id}", summary="删除文档")
async def delete_document(
        kb_id: UUID,
        doc_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, kb_id, doc_id)
    return success(message="删除成功")


@router.get("/{doc_id}/raw", summary="后端代理下载（仅 Local 后端）")
async def get_document_raw(
        kb_id: UUID,
        doc_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> StreamingResponse:
    """Local 模式专用：后端读字节流吐给客户端。

    R2 模式应直接走 R2 直链（download-url 返预签名 GET），此端点拒绝以省服务器出站。
    """
    if storage.supports_presigned:
        raise ValidationException(
            "当前存储后端支持预签名下载，请改走 download-url",
        )

    doc = await svc.get_by_id(current_user, kb_id, doc_id)
    content = await storage.read(doc.storage_key)
    safe = doc.name.replace('"', "").replace("\r", "").replace("\n", "")
    encoded = quote(safe, safe="")
    return StreamingResponse(
        BytesIO(content),
        media_type=_content_type_for(doc.file_type),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe}"; filename*=UTF-8\'\'{encoded}'
            ),
        },
    )


@router.get("/{doc_id}/download-url", summary="获取下载链接")
async def get_document_download_url(
        kb_id: UUID,
        doc_id: UUID,
        current_user: CurrentUserDep,
        svc: DocumentServiceDep,
) -> ResponseModel[dict[str, str]]:
    """两种后端返不同形态的 URL，前端拿到直接用：

        - R2 → 返预签名 GET URL（R2 直链，1 小时有效，不经后端省出站）
        - Local → 返后端 /raw 端点路径（前端打这个 URL，后端 StreamingResponse 吐字节）
    """

    doc = await svc.get_by_id(current_user, kb_id, doc_id)

    if storage.supports_presigned:
        url = await storage.generate_download_url(
            doc.storage_key, expires=3600, filename=doc.name,
        )
    else:
        url = f"/knowledge-bases/{kb_id}/documents/{doc.id}/raw"
    return success(data={"url": url})
