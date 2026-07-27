"""Skill 列表端点 —— 列出当前可挂载的 skill。

GET /skills  →  内置 skill（从内存注册表读，不查 DB）。

内置 skill 的本体随代码分发、不进 skills 表（设计稿决策 3），所以直接读注册表、
不走 service。用户上传的那批落 DB，将来在此合并（注册表 + 表查询），出参结构不变。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.skill import SkillOut
from app.services.skill.builtin import list_builtin_skills


router = APIRouter(prefix="/skills", tags=["skills"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]

@router.get("", summary="列出可挂载的 skill")
async def list_available_skills(
        _user: CurrentUserDep,
) -> ResponseModel[list[SkillOut]]:
    # 内置显式构造：BuiltinSkill 上没有 source_type 这个属性（它恒为 builtin，
    # 存进 dataclass 是冗余）。用户上传的那批是 DB 行、自带该字段，
    # 到时候走 SkillOut.model_validate(row) —— schema 的 from_attributes 是为它留的。
    skills = [
        SkillOut(
            name=s.name,
            description=s.description,
            source_type="builtin",
            required_env=list(s.required_env),
        )
        for s in list_builtin_skills()
    ]
    return success(data=skills)
