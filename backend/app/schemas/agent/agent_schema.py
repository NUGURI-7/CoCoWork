from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field



class AgentCreate(BaseModel):
    """创建 Agent 请求体。"""
    name: str = Field(min_length=1, max_length=150, description="Agent 名字")
    description: str = Field(default="", max_length=500, description="描述")
    template: str = Field(min_length=1, max_length=64, description="引用的内置模板 key")
    config: dict[str, Any] = Field(default_factory=dict, description="填料：行为 + 挂载资源")


class AgentUpdate(BaseModel):
    """更新 Agent 请求体。template 创建后锁死（要换形态 = 重建）。"""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] | None = None

class AgentOut(BaseModel):
    """Agent 对外输出。"""

    id: UUID
    name: str
    description: str
    template: str
    config: dict[str, Any]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentBriefOut(BaseModel):
    """Agent 选择器的一项 —— 只给员工看得懂、用得上的字段。

    刻意不含 config：管理员建的 Agent 里有模型、Prompt、知识库这些配置，
    员工端不该看见。
    """

    id: UUID
    name: str
    description: str
    avatar_url: str | None
    usable: bool = Field(description="能否发消息；false = 已下线，只能翻看历史会话")
    own: bool = Field(description="是不是自己建的；前端据此把管理员提供的单独列成一栏")


class TemplateOut(BaseModel):
    """内置模板对外输出 —— 注册表里的出厂元数据。

    刻意不含 base_prompt：那是模板出厂的脚手架，属于内部实现，前端不该看见
    也不该依赖。用户想知道「这个模板怎么干活」看 description。

    from_attributes 是为了直接吃模板类实例 —— 那几个字段都是 ClassVar，
    按属性取得到。
    """

    key: str = Field(description="注册表 key，创建 Agent 时原样传回 AgentCreate.template")
    name: str
    description: str
    form: Literal["loop", "graph"] = Field(description="编排形态，前端据此显示徽标")
    category: Literal["general", "business"] = Field(description="business 只对管理员列出")
    config_fields: list[str] | None = Field(
        default=None, description="管理员可配置的项；为空表示全部开放",
    )

    model_config = ConfigDict(from_attributes=True)
