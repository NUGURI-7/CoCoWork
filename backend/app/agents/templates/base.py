"""模板基类：把 1 + N 落到代码结构。

模板 = 出厂图配方，分两半：元数据（类属性）+ 图代码（build()，接 LLM 那片再实现）。
- AgentTemplate：所有模板共有的出厂元数据 + 抽象 build()
- LoopTemplate：loop 侧，那唯一的可配置引擎；build() 走共享 create_agent 工厂
- GraphTemplate：graph 侧，build() 每个模板各自手写 StateGraph

具体模板继承 LoopTemplate / GraphTemplate，设类属性 + @register 注册。
工具字段存 key 占位，跑前装配去注册表解析；能力不在模板、归实例 config（见 agent-templates-v1.md §4）。
"""

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langchain.agents.middleware import AgentMiddleware

class AgentTemplate(ABC):
    """内置模板基类：所有模板共有的出厂元数据 + build() 钩子。"""

    key: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    form: ClassVar[Literal["loop", "graph"]]
    base_prompt: ClassVar[str] = ""
    builtin_tools: ClassVar[list[str]] = []  # 内置工具 key 占位
    recommended_slots: ClassVar[list[str]] = []  # 建议挂载类型，仅提示

    @abstractmethod
    def build(
            self,
            *,
            chat_model: BaseChatModel,
            system_prompt: str | None,
            tools: list[BaseTool],
            middleware: list[AgentMiddleware] | None = None,
    ) -> CompiledStateGraph:
        """据模板配方 + 注入的 config 构建 CompiledStateGraph。

        Args:
            chat_model: runner build_chat_model 出的 LangChain BaseChatModel
            system_prompt: 实例 config.system_prompt（覆盖 base_prompt 用）
            tools: 装配器解析 capabilities / 内置工具 / mcp 后的 BaseTool 列表（P0 空）
            middleware: 装配器按需挂的能力 middleware（如 skill 的文件/执行工具）。
                没挂 skill 时为空 —— 那 7 个文件工具一个都不出现。
        """

        ...


class LoopTemplate(AgentTemplate):
    """loop 模板：共享 create_agent 工厂，靠数据（工具 / 能力 mw / prompt）区分。"""

    form: ClassVar[Literal["loop", "graph"]] = "loop"

    def build(
            self,
            *,
            chat_model: BaseChatModel,
            system_prompt: str | None,
            tools: list[BaseTool],
            middleware: list[AgentMiddleware] | None = None,

    ) -> CompiledStateGraph:
        """共享 create_agent 工厂 —— Augmented LLM 基线。

    Prompt 合成：模板 base_prompt 在前 + 实例 system_prompt 在后，双换行分隔。

    语义：base_prompt 是模板出厂的脚手架（能力描述 / 行为约束 / 工具说明），
    实例 system_prompt 是用户对该实例的角色 / 风格 / 任务特化 —— 二者叠加
    而非覆盖。任一为空则只用另一段；都为空则空字符串（create_agent 接受）。
    """
        parts = [p for p in (self.base_prompt, system_prompt) if p]
        prompt = "\n\n".join(parts)
        return create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=prompt,
            middleware=middleware or [],
        )


class GraphTemplate(AgentTemplate):
    """graph 模板：每个自带一份手写 StateGraph，build() 各自实现。"""
    form: ClassVar[Literal["loop", "graph"]] = "graph"
