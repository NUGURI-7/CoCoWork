"""工具注册表：进程内单例集合，name → CoCoTool 实例。

@register_tool 是类装饰器：import 到带它的工具类时，立即实例化、校验、按 name 登记。
- name 校验：必须符合 LLM function-calling 正则（^[a-zA-Z0-9_-]{1,64}$）——
  把「中文名 / 空格 / 点 / 非法字符」挡在启动期 fail fast，而非运行时被 LLM API 打回 400。
- 防环铁律：本文件只 import base，绝不 import 具体工具（依赖单向，
  靠 builtin/__init__ 的 import 触发各工具注册）。
"""

import logging
import re

from app.tools.base import CoCoTool

logger = logging.getLogger(__name__)

# LLM function-calling name 约束：OpenAI ^...{1,64}$ / Anthropic {1,128}$，取更严的 64。
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

_REGISTRY: dict[str, CoCoTool] = {}

def register_tool(cls: type[CoCoTool]) -> type[CoCoTool]:
    """类装饰器：实例化并按 name 注册；name 非法或重复直接报错。

    必须 return cls —— 否则被装饰的类名会被绑成 None。
    """
    instance = cls()

    if not _NAME_PATTERN.match(instance.name):
        raise ValueError(
            f"工具 name 非法：{instance.name!r} —— 须匹配 {_NAME_PATTERN.pattern}"
            "（LLM function-calling 限制，不能含中文 / 空格 / 点）"
        )
    if instance.name in _REGISTRY:
        raise ValueError(f"工具 name 重复：{instance.name}")

    _REGISTRY[instance.name] = instance
    return cls

def get_tool(name: str) -> CoCoTool | None:
    return _REGISTRY.get(name)


def list_tools() -> list[CoCoTool]:
    return list(_REGISTRY.values())

def resolve_tools(names: list[str]) -> list[CoCoTool]:
    """按 name 列表解析为工具实例 —— 装配器用。

    找不到的 name 跳过 + 告警（容错：工具下架 / 配置残留不该让整个 agent 跑不起来）。
    """
    resolved: list[CoCoTool] = []
    for name in names:
        tool = _REGISTRY.get(name)
        if tool is None:
            logger.warning("未知工具 name，跳过装配：%r", name)
            continue
        resolved.append(tool)
    return resolved