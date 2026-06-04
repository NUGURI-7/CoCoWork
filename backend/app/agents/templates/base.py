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
    def build(self):
        """据模板配方 + 注入的 config 构建 CompiledStateGraph（接 LLM 那片实现）。"""
        ...


class LoopTemplate(AgentTemplate):
    """loop 模板：共享 create_agent 工厂，靠数据（工具 / 能力 mw / prompt）区分。"""

    form: ClassVar[Literal["loop", "graph"]] = "loop"

    def build(self):
        """共享 create_agent 工厂——读自身字段装配（接 LLM 那片实现一次，4 条复用）。"""

        raise NotImplementedError(f"{self.key}: loop build 待接入 create_agent")


class GraphTemplate(AgentTemplate):
    """graph 模板：每个自带一份手写 StateGraph，build() 各自实现。"""
    form: ClassVar[Literal["loop", "graph"]] = "graph"
