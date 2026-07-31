"""取回被截断的工具结果 —— 把历史里那截省略号背后的全文捞回来。

**为什么需要它**：历史里超过 MAX_TOOL_OUTPUT_CHARS 的工具结果只留前 500 字
+ 一个 tool_use_id（见 view_context_assembler._cap_result）。全文一直躺在
messages.content 的 jsonb 里，这个工具就是那座桥 —— 没有它，截断就退化成
纯粹的信息丢失。

**per-run bound 实例**，形态同 ArtifactFetchTool：构造时绑本次回复的
conversation，装配阶段实例化，不进 registry（离开 workspace 对话它毫无意义，
不该让用户去勾）。
"""

from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.runtime.blocks import ToolUseBlock, parse_blocks
from app.models import Message
from app.tools.base import CoCoTool

_DESCRIPTION = """读取历史里被截断的工具结果全文。

历史消息中出现 `[结果过长已截断，完整 N 字符，需要全文请调 read_tool_result(...)]`
时，说明那次调用的返回只给了开头一截。要看全文就用本工具，传标记里那个 tool_use_id。

只对**历史**里的调用有效。本次回复中刚执行的工具，结果已经是完整的，不需要它。"""


class ToolResultFetchInput(BaseModel):
    tool_use_id: str = Field(
        ..., description="要取回的那次调用的 id，与截断标记里给出的一致"
    )


class ToolResultFetchTool(CoCoTool):
    """取回本对话历史里某次工具调用的完整结果。"""

    name: str = "read_tool_result"
    display_name: str = "读取完整工具结果"
    description: str = _DESCRIPTION
    args_schema: type[BaseModel] = ToolResultFetchInput

    # 本工具的存在意义就是吐出超过常规上限的内容，用默认的 4000 等于白跑一趟。
    # 仍然留个上限：万一哪个 MCP 返了几百 KB，基类那句截断提示也比撑爆窗口体面
    max_output_chars: int = 50_000

    # ---- per-run bound field（构造时必传）----
    conversation_id: UUID  # 可取范围的全部边界，服务端注入，绝不接受模型输入

    async def _execute(self, tool_use_id: str) -> str:
        # 归属边界就是 conversation_id 这一个条件，且它进了 WHERE ——
        # 不存在「查到了但忘了判权限」这个中间状态，范围恰好等于模型在历史里
        # 看得见的那些。`content @> '[{"id": …}]'` 让 PG 直接在 jsonb 里定位，
        # 不必把整段历史捞回来自己翻
        messages = await Message.filter(
            conversation_id=self.conversation_id,
            content__contains=[{"id": tool_use_id}],
        ).order_by("created_at")

        for m in messages:
            for b in parse_blocks(m.content):
                if isinstance(b, ToolUseBlock) and b.id == tool_use_id:
                    # 有这次调用但没有结果 = 当时被中断了。据实说，别让模型
                    # 以为是 id 传错了、反复重试
                    return b.result_text or "那次调用没有留下结果（当时被中断，或工具没有返回内容）。"

        # 错误要可执行：告诉它去哪儿找对的 id，而不是只说一句「没有」
        return (
            f"本对话历史里没有 id 为「{tool_use_id}」的工具调用。"
            "可取的只有历史消息中 [结果过长已截断…] 标记里给出的那个 id，请照它重试。"
        )
