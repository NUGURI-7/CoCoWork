from typing import ClassVar

from app.agents.templates.base import LoopTemplate
from app.agents.templates.registry import register

@register
class GeneralTemplate(LoopTemplate):
    """通用对话型：Augmented LLM 光板基线，无能力 middleware。"""

    key: ClassVar[str] = "general"
    name: ClassVar[str] = "通用对话型"
    description: ClassVar[str] = "基线对话助手"











