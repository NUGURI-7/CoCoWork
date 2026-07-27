"""内置 skill 注册表：启动时扫一次目录，之后只读内存。

内置 skill 的本体随代码分发（app/skills/builtin/<name>/），**永远不进 skills 表**。
表里只可能有一种内置行 —— 用户给某个内置 skill 填了 key 时产生的凭据行；
不需要 key 的内置 skill 在表里零行。故这里没有 seed，只有「扫描 + 校验」。

与 app/tools 注册表同姿势（list_ / get_ / resolve_）。区别：工具靠 @register_tool
在 import 时自注册，skill 是目录、只能扫盘，故收在 load_builtin_skills() 里
由 lifespan 显式调一次。
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from skills_ref import SkillProperties, read_properties, validate

from app.core.encryption import decrypt
from app.models import User
from app.models.skill import Skill, SkillSource

logger = logging.getLogger(__name__)

# app/services/skill/builtin.py → parents[2] 即 app/
BUILTIN_ROOT = Path(__file__).resolve().parents[2] / "skills" / "builtin"


@dataclass(frozen=True, slots=True)
class BuiltinSkill:
    """一个内置 skill 的不可变描述。本体在 directory 下，随代码走。"""

    name: str
    description: str
    directory: Path
    required_env: tuple[str, ...]  # 空 = 不需要 key，该 skill 在 skills 表里永远零行


_REGISTRY: dict[str, BuiltinSkill] = {}


def load_builtin_skills() -> None:
    """扫描并校验全部内置 skill，填入注册表。lifespan 启动时调一次。

    校验失败直接抛，进程起不来 —— 内置包是我们自己写的，不合规是开发期 bug，
    不是运行期容错项。静默跳过的后果是「挂上了但 LLM 从来不用」，最难查的那种。
    """
    _REGISTRY.clear()
    if not BUILTIN_ROOT.is_dir():
        logger.warning("内置 skill 目录不存在：%s", BUILTIN_ROOT)
        return

    for directory in sorted(p for p in BUILTIN_ROOT.iterdir() if p.is_dir()):
        if not (directory / "SKILL.md").is_file():
            continue
        errors = validate(directory)
        if errors:
            raise RuntimeError(
                f"内置 skill {directory.name} 不符合 Agent Skills 规范：{'；'.join(errors)}"
            )
        props = read_properties(directory)
        _REGISTRY[props.name] = BuiltinSkill(
            name=props.name,
            description=props.description,
            directory=directory,
            required_env=_required_env(props),
        )

    logger.info("内置 skill 已加载：%s", "、".join(_REGISTRY) or "（无）")


def list_builtin_skills() -> list[BuiltinSkill]:
    """全部内置 skill —— 前端列表一律显示，与用户在表里有没有行无关。"""
    return list(_REGISTRY.values())


def get_builtin_skill(name: str) -> BuiltinSkill | None:
    return _REGISTRY.get(name)


def resolve_builtin_skills(names: Sequence[str]) -> list[BuiltinSkill]:
    """按 AgentConfig.builtin_skills 解析出挂载的内置 skill，未知 name 静默跳过。

    容错策略对齐 resolve_tools / assemble_tools：残留配置（改名、下架）
    不该让整个 agent 起不来。
    """
    return [_REGISTRY[n] for n in names if n in _REGISTRY]


def _required_env(props: SkillProperties) -> tuple[str, ...]:
    """metadata.required-env → 环境变量名元组，空格分隔（形态对齐 allowed-tools）。

    这是给前端的**预填提示**（摆几个 key 输入框、分别叫什么），**不是白名单** ——
    key 编辑器允许用户自己加行（同 MCPServer.headers）。所以包里没声明
    不等于不能配 key，从聚合站下来的包不写这个也不用改包。
    """
    raw = (props.metadata or {}).get("required-env", "")
    return tuple(raw.split())


async def fetch_builtin_credentials(user: User, names: Sequence[str]) -> dict[str, str]:
    """取用户为这些内置 skill 配的 key，合并成一个环境变量 dict。

    没配 key 的内置 skill 在 skills 表里没有行，自然不出现在结果里 ——
    「零行」不是异常状态，是默认状态。
    """
    if not names:
        return {}

    rows = await Skill.filter(
        created_by=user,
        source_type=SkillSource.BUILTIN,
        name__in=list(names),
    )

    env: dict[str, str] = {}

    for row in rows:
        if not row.credentials_encrypted:
            continue
        for key, value in json.loads(decrypt(row.credentials_encrypted)).items():
            if key in env:
                logger.warning("环境变量 %s 被多个 skill 声明，后者覆盖前者", key)
            env[key] = value
    return env