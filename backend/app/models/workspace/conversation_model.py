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
- `created_by` 记发起人，工作空间会话与独立 Agent 会话都填，归属以它为准
- `workspace` 与 `agent_key` 恰好填一个，由数据库检查约束保证
- 不加 `last_message_at` / `message_count`：updated_at 触发足够支撑列表排序，
  count 用 ORM annotate，避免冗余维护成本（业界 v1 通用做法）
- workspace 删则连带删（CASCADE）
"""

from tortoise import fields
from tortoise.migrations.constraints import CheckConstraint

from app.models.base import TimestampMixin, UUIDBaseModel


class Conversation(UUIDBaseModel, TimestampMixin):
    """一条对话流：属于某个工作空间，或属于某个独立 Agent，二者必居其一。"""

    created_by = fields.ForeignKeyField(
        "models.User", related_name="conversations", on_delete=fields.CASCADE,
        db_index=True,
        description="发起人。会话归属以它为准",
    )
    workspace = fields.ForeignKeyField(
        "models.Workspace", related_name="conversations", on_delete=fields.CASCADE,
        null=True,
        description="工作空间会话填此项；独立 Agent 会话为 NULL",
    )
    agent_key = fields.CharField(
        max_length=64, null=True,
        description="独立 Agent 会话填该 Agent 在代码里的固定标识；工作空间会话为 NULL",
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
        constraints = (
            CheckConstraint(
                check="num_nonnulls(workspace_id, agent_key) = 1",
                name="conversations_workspace_xor_agent",
            ),
        )
