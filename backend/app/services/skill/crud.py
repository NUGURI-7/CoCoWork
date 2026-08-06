"""用户上传 skill 的增删查。

内置 skill 不经过这里 —— 它们住在内存注册表（builtin.py），本模块只碰
skills 表里那些 source_type=user 的行。
"""

import io
from uuid import UUID

from tortoise.exceptions import IntegrityError

from app.core.exceptions.types import Conflict409, NotFound404
from app.core.storage import storage
from app.models import User
from app.models.skill import Skill, SkillSource
from app.schemas.skill import SkillOut
from app.services.skill.builtin import get_builtin_skill, list_builtin_skills
from app.services.skill.package import load_skill_manifest, precheck_archive


async def create_skill(user: User, raw: bytes) -> Skill:
    """收一个 skill zip：校验 → 入库 → 存包。

    Raises:
        ValidationException: 包不合规（规模 / zip 结构 / SKILL.md）。
        Conflict409: name 撞上内置的，或撞上这个用户自己传过的。
    """
    precheck_archive(raw)
    props = load_skill_manifest(raw)

    if get_builtin_skill(props.name):
        raise Conflict409(f"内置 skill 已占用「{props.name}」这个名字，请改 SKILL.md 里的 name")

    try:
        skill = await Skill.create(
            created_by=user,
            name=props.name,
            description=props.description,
            source_type=SkillSource.USER,
            # (created_by, name) 唯一，故这个 key 天然不撞，不必再掺 skill.id
            storage_key=f"skills/{user.id}/{props.name}.zip",
        )
    except IntegrityError as exc:
        raise Conflict409(f"你已经传过一个叫「{props.name}」的 skill 了") from exc

    try:
        await storage.save(skill.storage_key, io.BytesIO(raw), content_type="application/zip")
    except Exception:
        # 包没存成，这行就是个指向空处的索引，留着比没有更糟
        await skill.delete()
        raise

    return skill


async def list_skills(user: User) -> list[SkillOut]:
    """这个用户当前能挂载的全部 skill：内置在前，自己传的在后。"""
    builtin = [
        SkillOut(
            name=s.name,
            description=s.description,
            source_type=SkillSource.BUILTIN,
            required_env=list(s.required_env),
        )
        for s in list_builtin_skills()
    ]
    rows = await Skill.filter(created_by=user).order_by("-created_at")
    return builtin + [SkillOut.model_validate(row) for row in rows]


async def get_own_skill(user: User, skill_id: UUID) -> Skill:
    """按 id 取一个这个用户自己上传的 skill。

    内置 skill 不在 skills 表里、也没有 id，故一律落进 404 —— 归属校验和
    「内置不给下载」是同一条判断，不必分开写。

    Raises:
        NotFound404: 不存在，或不属于这个用户。
    """
    skill = await Skill.get_or_none(id=skill_id, created_by=user)
    if skill is None:
        raise NotFound404("skill 不存在")
    return skill


async def delete_skill(user: User, skill_id: UUID) -> None:
    """删掉一个自己上传的 skill。"""
    skill = await get_own_skill(user, skill_id)
    await storage.delete(skill.storage_key)
    await skill.delete()
