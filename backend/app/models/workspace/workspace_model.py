"""Workspace 数据模型。

Workspace = 用户的工作空间：装一群 Agent 协作完成任务的"舞台"。

本表只存壳本身（name / description / avatar / 创建者 + supervisor + config）；
住进来的 Agent 实例走子表 `workspace_members`；
对话流走子表 `conversations`；消息走 `messages`。

两个 jsonb 字段分工：
- `supervisor`：内置管家的完整配置（复用 AgentConfig schema），
  workspace 自带、不可删除、不在 agents 表里独立存。
  作用域绑定 workspace：删 workspace 即销毁。
- `config`：workspace 自身的扁平配置——路由策略 / 开场白 /
  工作空间级挂载的 KB / 工具 / MCP id 数组 / 招募白名单 / UI 偏好。
  强类型由 Pydantic `WorkspaceConfig` 兜（extra="forbid"）。
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class Workspace(UUIDBaseModel, TimestampMixin):
    """工作空间本体。"""

    created_by = fields.ForeignKeyField(
        "models.User", related_name="workspaces", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=150, description="工作空间名字")
    description = fields.CharField(max_length=500, default="", description="简介")
    avatar_url = fields.CharField(max_length=500, default="", description="头像 URL")

    supervisor = fields.JSONField(
        default=dict,
        description="内置管家配置（复用 AgentConfig schema：model / prompt / knowledge / tools）",
    )
    config = fields.JSONField(
        default=dict,
        description="工作空间自身配置：路由策略 / 开场白 / 共享资源 id / 招募白名单 / UI 偏好",
    )

    class Meta:
        table = "workspaces"