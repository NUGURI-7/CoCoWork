"""Skill 端点：列出 / 上传 / 删除 / 下载。

GET    /skills                         →  内置（内存注册表）+ 用户上传（DB），合并成一份
POST   /skills                         →  传一个 zip 包
DELETE /skills/{skill_id}              →  删自己传的那份（内置没有 id，删不了）
GET    /skills/{skill_id}/download-url →  取下载链接（R2 直链 / Local 走 /raw）
GET    /skills/{skill_id}/raw          →  Local 后端专用，后端中转吐字节

都薄，合并、校验与归属判断住在 services/skill/crud.py。
"""

from io import BytesIO
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.core.depends import get_current_user
from app.core.exceptions.types import ValidationException
from app.core.http import ResponseModel, success
from app.core.storage import storage
from app.models.user import User
from app.schemas.skill import SkillOut
from app.services.skill.crud import create_skill, delete_skill, get_own_skill, list_skills
from app.services.skill.package import MAX_ARCHIVE_BYTES


router = APIRouter(prefix="/skills", tags=["skills"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", summary="列出可挂载的 skill")
async def list_available_skills(user: CurrentUserDep) -> ResponseModel[list[SkillOut]]:
    return success(data=await list_skills(user))


@router.post("", summary="上传 skill 包")
async def upload_skill(
        user: CurrentUserDep,
        file: Annotated[UploadFile, File(description="skill zip 包")],
) -> ResponseModel[SkillOut]:
    # 多读 1 字节：读满就说明超限，交给 precheck_archive 报错，
    # 不必把一个几百兆的包整个吞进内存才发现不该收
    raw = await file.read(MAX_ARCHIVE_BYTES + 1)
    return success(data=SkillOut.model_validate(await create_skill(user, raw)))


@router.delete("/{skill_id}", summary="删除上传的 skill")
async def remove_skill(user: CurrentUserDep, skill_id: UUID) -> ResponseModel[None]:
    await delete_skill(user, skill_id)
    return success()


@router.get("/{skill_id}/raw", summary="后端代理下载（仅 Local 后端）")
async def get_skill_raw(user: CurrentUserDep, skill_id: UUID) -> StreamingResponse:
    """Local 模式专用：后端读字节流吐给客户端。

    R2 模式应直接走 R2 直链（download-url 返预签名 GET），此端点拒绝以省服务器出站。

    注：本地与部署环境都跑 `STORAGE_BACKEND=r2`，故这条分支实际未被走到、也未经
    实机验证 —— 它在这里是为了跟知识库文档 / 沙箱产物同一口径，换存储后端不至于崩。
    """
    if storage.supports_presigned:
        raise ValidationException("当前存储后端支持预签名下载，请改走 download-url")

    skill = await get_own_skill(user, skill_id)
    content = await storage.read(skill.storage_key)
    # name 来自用户包里的 SKILL.md frontmatter，拼进响应头前先去掉引号与换行
    safe = f"{skill.name}.zip".replace('"', "").replace("\r", "").replace("\n", "")
    encoded = quote(safe, safe="")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe}"; filename*=UTF-8\'\'{encoded}'
            ),
        },
    )


@router.get("/{skill_id}/download-url", summary="获取下载链接")
async def get_skill_download_url(
        user: CurrentUserDep, skill_id: UUID,
) -> ResponseModel[dict[str, str]]:
    """两种后端返不同形态的 URL，前端拿到直接用：

        - R2 → 返预签名 GET URL（R2 直链，1 小时有效，不经后端省出站）
        - Local → 返后端 /raw 端点路径（前端打这个 URL，后端 StreamingResponse 吐字节）
    """
    skill = await get_own_skill(user, skill_id)

    if storage.supports_presigned:
        url = await storage.generate_download_url(
            skill.storage_key, expires=3600, filename=f"{skill.name}.zip",
        )
    else:
        url = f"/skills/{skill.id}/raw"
    return success(data={"url": url})
