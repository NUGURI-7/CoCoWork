"""AgentSpec —— runner 的输入契约。

不绑场景、不绑数据来源:
  Agent ORM / Workspace supervisor / 临时 NPC ...
任何"能跑的 agent" 都能转成 AgentSpec, 然后丢给 prepare_stream。
未来加新来源 = 加 factory 方法, runner 主体不动。
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.schemas.agent.config_schema import AgentConfig

if TYPE_CHECKING:
    from app.models import Agent

@dataclass(frozen=True)
class AgentSpec:
    """运行时 agent 规格 —— 强类型 config + 模板引用 key。"""

    template: str
    config: AgentConfig

    @classmethod
    def from_agent(cls, agent: "Agent") -> "AgentSpec":
        """从用户的 Agent ORM 实例构造。"""
        return cls(
            template=agent.template,
            config=AgentConfig.model_validate(agent.config),
        )

    @classmethod
    def from_jsonb(
            cls, data: dict[str, Any], default_template: str = "general",
    ) -> "AgentSpec":
        """从 jsonb dict 构造(用于 workspace.supervisor 等 jsonb 存储)。

        template 字段优先从 dict 里取, 没有则 fallback 到 default_template。
        """
        return cls(
            template=data.get("template", default_template),
            config=AgentConfig.model_validate(data),
        )

