"""Agent 数据模型。

Agent = 用户基于内置模板装备好的资产（= 架构里的 NPC）：
引用一个模板（代码里的图配方，存字符串 key）+ 一身填料（config）。

模板本身是代码、不建表；config 是 jsonb，装「行为 + 挂载资源」：
- 行为：loop → {prompt, model}；graph → {nodes: {<节点名>: {prompt, model}}}
- 资源：knowledge / tools / skills 的 id 列表（v1 走 jsonb，不建关联表）

loop / graph 由 `template` 决定；跑前装配时拿 key 取代码配方 + 把 config 注进去。
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class Agent(UUIDBaseModel, TimestampMixin):
    """用户创建的 Agent（NPC）：模板引用 + config 填料。"""

    created_by = fields.ForeignKeyField(
        "models.User", related_name="agents", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=150, description="Agent 名字")
    description = fields.CharField(max_length=500, default="", description="描述")
    template = fields.CharField(
        max_length=64,
        description="引用的内置模板 key（如 researcher / ppt），指向代码里的模板注册表",
    )

    config = fields.JSONField(
        default=dict,
        description="填料：行为（prompt/model）+ 挂载资源（knowledge/tools/skills 的 id 列表）",
    )

    class Meta:
        table = "agents"