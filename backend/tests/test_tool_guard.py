"""工具护栏 —— 直接驱动中间件的 awrap_tool_call，零 LLM 调用。

护栏存在的理由是 MCP 工具不经 CoCoTool：它们是 langchain-mcp-adapters 按远端
server 声明动态生成的，超时 / 截断 / 异常兜底一样都没有，而框架自带的两道兜底
都只认 ToolException —— 传输层失败（连不上 server）会绕过它们直接炸掉整轮。

这里锁住：正常结果别乱动、异常转成 ToolMessage 而不是抛、超时也是、细节不外泄、
Command 不能被当文本截断、用户中断必须继续往上传。
"""

import asyncio

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agents.runtime.tool_guard import (
    GUARD_TIMEOUT_SECONDS,
    ToolGuardMiddleware,
    _timeout_for,
)
from app.tools.base import MAX_TOOL_OUTPUT_CHARS


class _Req:
    """够用的 ToolCallRequest 替身 —— 护栏只读 tool_call 里的 name / id 和 tool。

    tool 默认 None：真实契约里这个字段可以是 None（工具没注册到 ToolNode），
    正好也是「工具没自报超时」那一档。
    """

    def __init__(self, name: str = "web_search", call_id: str = "call_1", tool=None):
        self.tool_call = {"name": name, "id": call_id, "args": {}}
        self.tool = tool


def _handler_returning(result):
    async def _h(_req):
        return result
    return _h


def _handler_raising(exc: BaseException):
    async def _h(_req):
        raise exc
    return _h


async def test_正常结果原样透出():
    guard = ToolGuardMiddleware()
    msg = ToolMessage(content="搜到 3 条", tool_call_id="call_1")

    out = await guard.awrap_tool_call(_Req(), _handler_returning(msg))
    assert out is msg


async def test_异常转成消息而不是抛():
    """传输层失败正是框架两道兜底都够不着的那种 —— 必须在这里被拦住。"""
    guard = ToolGuardMiddleware()

    out = await guard.awrap_tool_call(
        _Req(), _handler_raising(ConnectionError("Connection refused: 10.0.0.5:8931"))
    )

    assert isinstance(out, ToolMessage)
    assert out.status == "error"
    assert out.tool_call_id == "call_1"
    assert "web_search" in out.content
    # 细节不喂给模型（栈 / URL / 凭据同理）
    assert "10.0.0.5" not in out.content
    assert "Connection refused" not in out.content


async def test_超时转成消息(monkeypatch):
    """不真等 60 秒：把闸门临时调到极小。护栏读的是模块级常量，patch 得到。"""
    import app.agents.runtime.tool_guard as tg

    monkeypatch.setattr(tg, "GUARD_TIMEOUT_SECONDS", 0.01)

    async def _slow(_req):
        await asyncio.sleep(5)

    out = await ToolGuardMiddleware().awrap_tool_call(_Req(), _slow)

    assert isinstance(out, ToolMessage)
    assert out.status == "error"
    assert "超时" in out.content


async def test_长跑工具不吃默认闸():
    """execute（沙箱命令）/ task（委派一整段子 agent）必须按预算表放宽。

    默认 60 秒罩住这两个，等于沙箱那套 600 秒上限和整段委派永远没机会跑完。
    """
    from app.services.skill.mount import EXECUTE_TIMEOUT_CEILING

    assert _timeout_for(_Req(name="execute"), "execute") > EXECUTE_TIMEOUT_CEILING
    assert _timeout_for(_Req(name="task"), "task") > GUARD_TIMEOUT_SECONDS


async def test_工具自报超时不被外层废掉():
    """CoCoTool 把 timeout_seconds 调到默认闸之上时，护栏得比它更有耐心。"""

    class _SlowTool:
        timeout_seconds = 90.0

    assert _timeout_for(_Req(tool=_SlowTool()), "artifact_fetch") > 90.0


async def test_没自报的落回默认闸():
    """MCP 动态工具这一档 —— 谁也不知道它要跑多久，只能给兜底值。"""
    assert _timeout_for(_Req(), "web_search") == GUARD_TIMEOUT_SECONDS


async def test_超长输出被截断():
    guard = ToolGuardMiddleware()
    long_text = "啊" * (MAX_TOOL_OUTPUT_CHARS + 500)
    msg = ToolMessage(content=long_text, tool_call_id="call_1")

    out = await guard.awrap_tool_call(_Req(), _handler_returning(msg))

    assert len(out.content) < len(long_text)
    assert "已截断" in out.content
    assert str(MAX_TOOL_OUTPUT_CHARS + 500) in out.content, "要告诉模型原始有多长"


async def test_不超长的不动():
    guard = ToolGuardMiddleware()
    msg = ToolMessage(content="短", tool_call_id="call_1")

    out = await guard.awrap_tool_call(_Req(), _handler_returning(msg))
    assert out is msg, "没超限时应原样返回，不要白白复制一份"


async def test_Command_不被当文本截断():
    """deepagents 的 task 返回 Command —— 那是状态更新不是文本，截了会破坏语义。"""
    guard = ToolGuardMiddleware()
    cmd = Command(update={"messages": []})

    out = await guard.awrap_tool_call(_Req(), _handler_returning(cmd))
    assert out is cmd


async def test_用户中断继续往上传():
    """CancelledError 继承 BaseException —— 掐断时不能被歪曲成「工具执行失败」。"""
    guard = ToolGuardMiddleware()

    with pytest.raises(asyncio.CancelledError):
        await guard.awrap_tool_call(_Req(), _handler_raising(asyncio.CancelledError()))
