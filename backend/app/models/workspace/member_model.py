"""WorkspaceMember 数据模型。

WorkspaceMember = workspace 招进来的普通成员（薄引用 Agent）。

设计要点：
- supervisor 不在本表（workspace 自带，存 `Workspace.supervisor` jsonb）
- 本表只装招进来的"普通成员"，每行 = (workspace, agent) 引用对
- agent 是引用不快照：用户改 agent，所有 workspace 里跟着变
- CASCADE：workspace 删 / agent 删，相关 member 自动连带清理
- unique (workspace_id, agent_id)：同一 agent 在同一 workspace 只能招一次
- `config` jsonb：留扩展口子，将来装 nickname / avatar 覆盖 / 该成员在此 workspace 的特化 prompt 等
- created_at 等价于"加入时间"，不再单设 joined_at 字段（对齐项目 TimestampMixin 范式）
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class WorkspaceMember(UUIDBaseModel, TimestampMixin):
    """workspace 招进来的普通成员（agent 引用）。"""

    workspace = fields.ForeignKeyField(
        "models.Workspace", related_name="members", on_delete=fields.CASCADE,
    )
    agent = fields.ForeignKeyField(
        "models.Agent", related_name="member_of", on_delete=fields.CASCADE,
    )

    config = fields.JSONField(
        default=dict,
        description="成员在此 workspace 的覆盖配置（nickname / avatar / 特化 prompt 等）",
    )

    class Meta:
        table = "workspace_members"
        unique_together = (("workspace", "agent"),)