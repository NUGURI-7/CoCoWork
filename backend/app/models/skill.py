"""Skill 定义（目录 + SKILL.md 形态，对齐 agentskills 开放标准）。

Skill 与 tool 在建模上同级（都是可挂载到 agent 的资源），但运行机制不同：
tool 是函数签名，LLM 填参数调用；skill 是一段说明书 + 捆绑脚本，
name/description 进 system prompt，正文与脚本在沙箱里由通用文件/shell 工具取用。

存储沿用 Document 的形态：本表只存元数据与对象存储的 key，zip 本体走 storage 抽象。
理由（Dify agent_drive_files 同构）：表是索引，不是文件柜。

内置 skill 与用户上传的 skill 共用同一条入库路径 —— 前者只是启动时 seed 进来的
种子数据，同样 per-user、同样可删改。刻意不做「共享的内置行」：那会让权限判断
分叉，且共享行挂不上 per-user 的凭据。
"""

from enum import StrEnum

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class SkillSource(StrEnum):
    """Skill 来源溯源。"""

    BUILTIN = "builtin"  # 随代码分发的预置包，启动时 seed 入库
    USER = "user"  # 用户上传


class Skill(UUIDBaseModel, TimestampMixin):
    """一个可挂载到 agent 的 skill。"""

    created_by = fields.ForeignKeyField(
        "models.User", related_name="skills", on_delete=fields.CASCADE, db_index=True,
    )
    name = fields.CharField(
        max_length=64,
        description="SKILL.md 的 name，LLM 可见标识（agentskills 规范：小写字母/数字/连字符，≤64）",
    )
    description = fields.CharField(
        max_length=1024,
        description="SKILL.md 的 description，进 system prompt 供 LLM 判断是否该用（规范上限 1024）",
    )
    source_type = fields.CharEnumField(
        SkillSource,
        max_length=16,
        default=SkillSource.USER,
        description="来源溯源：builtin 为预置包（seed 入库）/ user 为上传。仅用于 UI 区分与 seed 幂等判断，不是权限位——两者都可删改",
    )
    storage_key = fields.CharField(
        max_length=512,
        default="",
        description="zip 包在对象存储中的 key",
    )
    credentials_encrypted = fields.TextField(
        null=True,
        description="运行所需环境变量 dict（整体 JSON Fernet 加密，同 MCPServer.headers_encrypted）；运行时解密后经 docker run -e 注入；无则 NULL",
    )
    skill_metadata = fields.JSONField(
        default=dict,
        description="原包文件清单等展示用信息（抄 Dify skill_metadata）；运行必需的字段一律提成列，不塞这里",
    )
    enabled = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "skills"
