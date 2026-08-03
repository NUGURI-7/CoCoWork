"""Conversation 数据模型。

Conversation = workspace 里一条对话流，1 workspace : N conversations。
对应前端 conversation 切换条的每个 tab。

设计要点：
- **与 checkpointer 不是一对一**：thread_id 取的是「本轮 assistant 消息 id」，
  一次回复一个存档槽（见 runtime/runner.py 里配 configurable 那段）。原先约定
  按 conversation 粒度复用同一个槽，08-02 挂 checkpointer 时改口 —— 历史由业务侧
  按应答者视角每轮重算，复用同一个槽会让 add_messages 把上一轮的视角历史叠进来
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

    context_tokens = fields.IntField(
        db_default=0,
        description="最近一轮上下文 token 数(API usage 上报,层 B 压缩触发判据)",
    )

    class Meta:
        table = "conversations"
