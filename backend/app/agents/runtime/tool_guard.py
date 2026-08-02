"""工具调用护栏 —— 超时 / 输出截断 / 异常兜底，罩住所有来源的工具。

内置工具与知识库工具继承 `CoCoTool`，这三样是基类的模板方法给的；**MCP 工具
没有** —— 它们是 `langchain-mcp-adapters` 按远端 server 声明**动态生成**的
BaseTool，我们没写过它们一行代码，也没有地方给它们加。

框架自带的兜底够不着这一层，两道都漏：

- `ToolNode` 的 `_default_handle_tool_errors` 只把 `ToolInvocationError` 转成
  消息，其余一律 re-raise；
- `BaseTool.handle_tool_error` 只认 `ToolException`，而 `langchain-mcp-adapters`
  在源码注释里把契约写死了：**传输 / 会话失败不是 ToolException 子类，会绕过
  `handle_tool_error` 直接传播**（`tools.py` 的 `_MCPToolExecutionError` 文档）。

而「压根连不上 server」正是最常见的那种失败 —— 只有包在工具调用外面才拦得住。
一个 MCP 工具炸掉不该让整轮对话跟着死：模型收到一句「这个工具没成」，还能换个
方式或者跳过这一步。

挂在 middleware 列表**第一位** —— 框架规则是 first defined = outermost，
护栏得在最外层。
"""

import asyncio
import logging

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphBubbleUp
from langgraph.types import Command

from app.tools.base import MAX_TOOL_OUTPUT_CHARS

logger = logging.getLogger(__name__)

# 比 CoCoTool 自己的 30 秒明显宽 —— 这是最后一道闸，不是工具的定制策略。
# 定得跟内层一样，会把工具自己调大的超时（将来某个慢工具设 60 秒）当场废掉。
GUARD_TIMEOUT_SECONDS = 60.0


class ToolGuardMiddleware(AgentMiddleware):
    """所有工具调用的最外层护栏。

    `CancelledError` 继承 `BaseException`，不会被 `except Exception` 接住 ——
    用户掐断时工具调用正常取消，不会被歪曲成「执行失败」。
    """

    async def awrap_tool_call(self, request: ToolCallRequest, handler):
        name = request.tool_call.get("name") or "?"
        call_id = request.tool_call.get("id") or ""
        try:
            result = await asyncio.wait_for(handler(request), GUARD_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("工具执行超时 name=%s limit=%ss", name, GUARD_TIMEOUT_SECONDS)
            return ToolMessage(
                content=f"工具「{name}」执行超时（超过 {GUARD_TIMEOUT_SECONDS:g} 秒），本次没有结果。",
                tool_call_id=call_id,
                status="error",
            )
        except GraphBubbleUp:
            # LangGraph 的控制流信号（人工确认的中断、工具返回 Command 注入
            # state、图排空），全靠抛异常向上冒泡实现 —— **它们不是「工具失败」**。
            # 被下面那个 except Exception 截住的话，用户永远等不到那张表单，
            # 模型只会收到一句「执行失败」然后自顾自往下答（实测过一次）。
            # 顺序不能与下面对调：Python 按书写顺序匹配 except 分支。
            # 同 CoCoTool._arun 里那道口子 —— 两层兜底都得开，漏一层就白搭
            raise
        except Exception:
            # 细节只进日志 —— 栈 / URL / 凭据不喂给模型（同 adapter 的口径）
            logger.exception("工具执行失败 name=%s", name)
            return ToolMessage(
                content=f"工具「{name}」执行失败，本次没有结果。可以换个方式，或者跳过这一步。",
                tool_call_id=call_id,
                status="error",
            )
        return _cap_result(result, name)


def _cap_result(result, name: str):
    """只截 `ToolMessage` 的纯文本内容。

    `Command` 是状态更新不是文本（deepagents 的 task 就返回它），截了会破坏语义；
    多模态 content（内容块列表）也不动 —— 按字符截对图片块没有意义。

    上限复用 `CoCoTool` 那个常量，不另立一套：一次执行能进多少上下文，这里就是
    多少，跨轮回放（`view_context_assembler._cap_result`）也是同一个数。
    """
    if isinstance(result, Command) or not isinstance(result, ToolMessage):
        return result
    text = result.content
    if not isinstance(text, str) or len(text) <= MAX_TOOL_OUTPUT_CHARS:
        return result
    logger.info("工具输出超长已截断 name=%s 原始=%d 字符", name, len(text))
    kept = text[:MAX_TOOL_OUTPUT_CHARS]
    return result.model_copy(
        update={
            "content": (
                f"{kept}\n\n[输出过长已截断，原始共 {len(text)} 字符，"
                f"仅显示前 {MAX_TOOL_OUTPUT_CHARS}]"
            )
        }
    )
