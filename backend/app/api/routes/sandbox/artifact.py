"""沙箱产物的下载端点。

**URL 不提前给、点击时才换**：SSE 的 artifacts 帧里只有 id / 文件名 / 大小 / 类型，
没有下载 URL。用户点卡片才来这里换一个短期预签名 —— 于是每次点击都走一遍归属
校验，链接也不会长期有效，消息放三天再点照样能开。

**为什么不由后端代理字节**（Local 后端除外）：产物可能是 SVG，而 SVG 能内嵌
`<script>`。走预签名直链时它在对象存储的域上渲染，与应用域同源隔离；由后端
inline 吐出去则等于把脚本搬到应用域上执行，能读到 localStorage 里的 token。
用户生成内容放独立域是既有惯例（GitHub raw、Google usercontent 皆然）。
"""

from io import BytesIO
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.depends import get_current_user
from app.core.exceptions import NotFound404, ValidationException
from app.core.http import ResponseModel, success
from app.core.storage import storage
from app.models.sandbox import SandboxArtifact
from app.models.user import User

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]

# 预签名有效期：短到泄露了也没多大价值，长到够浏览器把文件拉完
_DOWNLOAD_URL_EXPIRES = 300


async def _get_user_artifact(artifact_id: UUID, user: User) -> SandboxArtifact:
    """取产物，归属条件写进 WHERE —— 不是你的就查不到，
        不存在「查到了但忘了判权限」这个中间状态。"""
    artifact = await SandboxArtifact.filter(id=artifact_id, created_by=user).first()
    if artifact is None:
        raise NotFound404("产物不存在")
    return artifact


@router.get("/{artifact_id}/download-url", summary="获取产物下载链接")
async def get_artifact_download_url(
        artifact_id: UUID,
        current_user: CurrentUserDep,
        disposition: Literal["inline", "attachment"] = "inline",
) -> ResponseModel[dict[str, str]]:
    """两种后端返不同形态的 URL，前端拿到直接打开：

        - R2 → 预签名直链
        - Local → 后端 /raw 端点路径

    `disposition` 由前端按用户点了什么决定：点卡片主体是「打开看」（inline），
    点下载图标是「存到本地」（attachment）。同一个产物两种用法，签两次即可 ——
    预签名是纯本地 HMAC 计算，不发网络请求，多签一次近乎免费。
    """
    artifact = await _get_user_artifact(artifact_id, current_user)

    if storage.supports_presigned:
        url = await storage.generate_download_url(
            artifact.storage_key,
            expires=_DOWNLOAD_URL_EXPIRES,
            filename=artifact.filename,
            disposition=disposition,
        )
    else:
        url = f"/artifacts/{artifact.id}/raw?disposition={disposition}"
    return success(data={"url": url})


@router.get("/{artifact_id}/raw", summary="后端代理下载（仅 Local 后端）")
async def get_artifact_raw(
        artifact_id: UUID,
        current_user: CurrentUserDep,
        disposition: Literal["inline", "attachment"] = "inline",
) -> StreamingResponse:
    """Local 模式专用：后端读字节流吐给客户端。

    R2 模式应走 download-url 拿直链，此端点拒绝以省服务器出站。
    """
    if storage.supports_presigned:
        raise ValidationException("当前存储后端支持预签名下载，请改走 download-url")

    artifact = await _get_user_artifact(artifact_id, current_user)
    content = await storage.read(artifact.storage_key)

    safe = artifact.filename.replace('"', "").replace("\r", "").replace("\n", "")
    encoded = quote(safe, safe="")

    return StreamingResponse(
        BytesIO(content),
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="{safe}"; filename*=UTF-8\'\'{encoded}'
            ),
            # 本端点走的是应用自己的域（开发环境），而 SVG 能内嵌 <script>。
            # sandbox 指令把这份响应关进一个无源沙箱：脚本不执行、也拿不到 cookie
            # 与 localStorage。R2 那条路靠「对象存储本就是另一个域」天然隔离，不需要这行。
            "Content-Security-Policy": "sandbox",
        },
    )