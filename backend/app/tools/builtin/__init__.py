"""内置工具注册触发：import 各工具模块，让 @register_tool 执行登记。

新增内置工具时，在此加一行 import 即可（不在此处 import = 注册不生效）。
"""

from app.tools.builtin import calculator  # noqa: F401  触发注册