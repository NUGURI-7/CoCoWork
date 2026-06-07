"""工具层包入口：import builtin 触发各内置工具的 @register_tool 注册。

registry 防环不 import 具体工具，注册触发就落在包入口 —— 只要有人
import app.tools.*，builtin 工具自动登记。（对齐 templates/__init__.py。）
"""

from app.tools import builtin  # noqa: F401  触发注册
from app.tools.base import CoCoTool
from app.tools.registry import get_tool, list_tools, register_tool, resolve_tools

__all__ = ["CoCoTool", "get_tool", "list_tools", "register_tool", "resolve_tools"]