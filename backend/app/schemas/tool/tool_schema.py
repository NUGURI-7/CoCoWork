"""工具出参 schema —— 工具列表接口的统一形态。

这几个字段是所有工具来源（内置 / MCP / custom）天生都有的元信息，新增来源
直接套同一个结构、不用改。内置工具从 registry 的 CoCoTool 实例读，
from_attributes 直接按属性映射。
"""

from pydantic import BaseModel, ConfigDict


class ToolOut(BaseModel):
    """一个可用工具的展示信息（前端工具列表 + Agent 工具选择器共用）。"""

    model_config = ConfigDict(from_attributes=True)

    name: str          # registry key，前端当 value、勾选后写进 config.builtin_tools
    display_name: str  # 中文名
    description: str   # 能力描述
    source_type: str   # builtin / mcp / custom —— 前端按这个分组
    category: str      # data_source / utility —— 能力分类，卡片上的标签
    dangerous: bool    # 有副作用（删文件 / 发请求 / 花钱）标记
