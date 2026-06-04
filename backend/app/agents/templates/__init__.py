from app.agents.templates import builtin  # noqa: F401  触发注册
from app.agents.templates.base import AgentTemplate
from app.agents.templates.registry import get_template, list_templates, register

__all__ = ["AgentTemplate", "get_template", "list_templates", "register"]