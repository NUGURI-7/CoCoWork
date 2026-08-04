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

from app.services.skill.mount import EXECUTE_TIMEOUT_CEILING
from app.tools.base import MAX_TOOL_OUTPUT_CHARS

logger = logging.getLogger(__name__)

# 兜底闸：给「谁也不知道它要跑多久」的工具用（MCP 动态工具是主力）。
# 比 CoCoTool 自己的 30 秒明显宽 —— 这是最后一道闸，不是工具的定制策略。
# 定得跟内层一样，会把工具自己调大的超时（将来某个慢工具设 60 秒）当场废掉。
GUARD_TIMEOUT_SECONDS = 60.0

# 工具自报超时之上再留的余量：内层那道闸响了之后还要拼错误消息、回传，护栏
# 必须比内层更有耐心，否则内层的定制超时等于没写（同 docker_sandbox._HTTP_MARGIN）。
GUARD_TIMEOUT_MARGIN = 15.0

# 点名放宽的工具 —— 它们不是「一次函数调用」，默认闸对它们是误伤：
#
# - execute：沙箱里跑一条 shell 命令，自带 120s 默认 / 600s 上限，真正掐它的是
#   容器里那条 `timeout` 命令；护栏卡 60 秒的话，那套上限从来没机会生效。
# - task：委派一个成员 = 一整段子 agent 运行（多次模型调用 + 若干工具），而里面
#   每个工具**已经各自被这同一个护栏罩过**。外面再压 60 秒是重复设限，还会把
#   跑到一半的成员整个掐掉。这里的 600 秒只兜「整段委派挂死」。
#   注意它比 execute 那档略小：成员真跑一条逼近 600 秒上限的沙箱命令时，是委派
#   先超时。实测 skill 脚本远够不着这个量级，先按 600 收着。
#
# 键是工具在 LLM 眼里的 name（deepagents 写死的两个字面量），不是中文展示名。
_TOOL_TIMEOUT_BUDGETS: dict[str, float] = {
    "execute": EXECUTE_TIMEOUT_CEILING + GUARD_TIMEOUT_MARGIN,
    "task": 600.0,
}


class ToolGuardMiddleware(AgentMiddleware):
    """所有工具调用的最外层护栏。

    `CancelledError` 继承 `BaseException`，不会被 `except Exception` 接住 ——
    用户掐断时工具调用正常取消，不会被歪曲成「执行失败」。
    """

    async def awrap_tool_call(self, request: ToolCallRequest, handler):
        name = request.tool_call.get("name") or "?"
        call_id = request.tool_call.get("id") or ""
        limit = _timeout_for(request, name)
        try:
            result = await asyncio.wait_for(handler(request), limit)
        except asyncio.TimeoutError:
            logger.warning("工具执行超时 name=%s limit=%ss", name, limit)
            return ToolMessage(
                content=f"工具「{name}」执行超时（超过 {limit:g} 秒），本次没有结果。",
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


def _timeout_for(request: ToolCallRequest, name: str) -> float:
    """这次调用给多少墙钟预算 —— 从具体到笼统三档。

    1. 预算表点名的（execute / task）：按表。
    2. 工具自报 `timeout_seconds` 的（`CoCoTool` 全家）：取「自报 + 余量」与默认闸
       的较大者。让内层那道闸先响 —— 它的报错话术带中文展示名、更像人话，护栏只
       在它没响（卡在 await 里根本回不来）时兜底。
    3. 其余：默认 60 秒。`request.tool` 可能是 None（没注册到 ToolNode 的调用），
       getattr 那行把这种情况一并吃掉，不额外判。
    """
    budget = _TOOL_TIMEOUT_BUDGETS.get(name)
    if budget is not None:
        return budget
    declared = getattr(request.tool, "timeout_seconds", None)
    if isinstance(declared, (int, float)):
        return max(float(declared) + GUARD_TIMEOUT_MARGIN, GUARD_TIMEOUT_SECONDS)
    return GUARD_TIMEOUT_SECONDS


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
