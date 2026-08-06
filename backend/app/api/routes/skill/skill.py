"""Skill 端点：列出 / 上传 / 删除。

GET    /skills            →  内置（内存注册表）+ 用户上传（DB），合并成一份
POST   /skills            →  传一个 zip 包
DELETE /skills/{skill_id} →  删自己传的那份（内置没有 id，删不了）

三个都薄，合并与校验住在 services/skill/crud.py。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.skill import SkillOut
from app.services.skill.crud import create_skill, delete_skill, list_skills
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
