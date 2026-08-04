from typing import ClassVar

from app.agents.templates.base import LoopTemplate
from app.agents.templates.registry import register

@register
class GeneralTemplate(LoopTemplate):
    """通用对话型：Augmented LLM 光板基线，无能力 middleware。"""

    key: ClassVar[str] = "general"
    name: ClassVar[str] = "General"
    description: ClassVar[str] = (
        "最基础的一档：模型自己决定何时调工具、查知识库、怎么把活干完。"
        "没有预设流程，适合绝大多数任务。"
    )











