"""Skill 出参 schema —— skill 列表接口的统一形态。

对齐 ToolOut 的思路：字段是所有来源（内置 / 用户上传）天生都有的元信息，
新增来源套同一个结构。用户上传的那批是 DB 行，走 from_attributes 直接映射；
内置的显式构造 —— BuiltinSkill 上没有 source_type 属性（它恒为 builtin，
存进 dataclass 是冗余）。
"""

from pydantic import BaseModel, ConfigDict


class SkillOut(BaseModel):
    """一个可挂载 skill 的展示信息（前端 skill 列表 + Agent 挂载选择器共用）。"""

    model_config = ConfigDict(from_attributes=True)

    name: str               # 规范里的 name，前端当 value、勾选后写进 config.builtin_skills
    description: str        # SKILL.md 的 description，同时也是进 system prompt 的那份
    source_type: str        # builtin / user —— 前端按这个分组
    required_env: list[str] # 该 skill 声明需要的环境变量名；空 = 不需要配 key