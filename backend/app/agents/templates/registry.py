"""模板注册表：进程内单例集合，key → 模板实例。

@register 是类装饰器：import 到带它的类时，立即把该类实例化、按 key 登记。
防环铁律：本文件只 import base，绝不 import 具体模板（依赖单向）。
"""

from app.agents.templates.base import AgentTemplate

_REGISTRY: dict[str, AgentTemplate] = {}

def register(cls: type[AgentTemplate]) -> type[AgentTemplate]:
    """类装饰器：实例化并按 key 注册；重复 key 直接报错。

        必须 return cls —— 否则被装饰的类名会被绑成 None。
    """
    instance = cls()

    if instance.key in _REGISTRY:
        raise ValueError(f"模板 key 重复：{instance.key}")
    _REGISTRY[instance.key] = instance

    return cls


def get_template(key: str) -> AgentTemplate | None:

    return _REGISTRY.get(key)

def list_templates() -> list[AgentTemplate]:
    return list(_REGISTRY.values())







