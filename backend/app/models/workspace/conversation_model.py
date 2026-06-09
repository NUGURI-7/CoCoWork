"""Conversation 数据模型。

Conversation = workspace 里一条对话流，1 workspace : N conversations。
对应前端 conversation 切换条的每个 tab。

设计要点：
- 跟 LangGraph checkpointer 一对一映射：`thread_id = conversation.id.hex`，
  conversation 即"会话线程"的业务库映射，运行时状态在 checkpointer 那侧
- title 可空字符串（新建对话还没起名）；系统可后续根据首条用户消息自动生成
- `config` jsonb 留扩展口子：对话级临时覆盖（换模型 / 开 thinking / 临时挂 KB），
  对齐 Workspace / Agent / Member 范式
- 不加 `created_by`：workspace.created_by 已能反查归属（单用户场景）；
  团队场景未来加权限时再补
- 不加 `last_message_at` / `message_count`：updated_at 触发足够支撑列表排序，
  count 用 ORM annotate，避免冗余维护成本（业界 v1 通用做法）
- workspace 删则连带删（CASCADE）
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class Conversation(UUIDBaseModel, TimestampMixin):
    """workspace 里的一条对话流。"""

    workspace = fields.ForeignKeyField(
        "models.Workspace", related_name="conversations", on_delete=fields.CASCADE,
    )
    title = fields.CharField(max_length=150, default="", description="对话标题")

    config = fields.JSONField(
        default=dict,
        description="对话级临时覆盖（换模型 / 开 thinking / 临时挂 KB 等扩展口子）",
    )

    class Meta:
        table = "conversations"