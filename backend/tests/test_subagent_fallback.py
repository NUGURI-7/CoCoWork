"""子 agent 失败兜底 —— 假 Runnable，零 LLM 调用。

deepagents 的 task 工具里 `await subagent.ainvoke(...)` 是裸调，子 agent 抛什么都
直接冒到 supervisor 那张图上，一个成员挂掉整轮对话跟着挂。兜底要把「炸了」翻译成
一条正常消息，让 supervisor 有机会改派 / 自己上 / 如实告诉用户。

这里锁三件事：正常路径别被碰、失败路径要返回 deepagents 取得到的形状、以及
用户中断不能被歪曲成「执行出错」。
"""

import asyncio

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.errors import GraphRecursionError

from app.agents.workspace.workspace import _with_failure_fallback

LABEL = "数据分析师"


def _ok(payload: dict) -> dict:
    return {"messages": [AIMessage(content="报表做好了")]}


def _raise(exc: BaseException):
    def _inner(payload: dict) -> dict:
        raise exc
    return _inner


async def test_正常路径原样透出():
    """兜底只在异常时介入 —— 没炸的时候不能改动任何东西。"""
    r = _with_failure_fallback(RunnableLambda(_ok), LABEL)
    out = await r.ainvoke({"messages": []})

    assert out["messages"][-1].content == "报表做好了"


async def test_失败时返回_deepagents_取得到的形状():
    """必须是 {"messages": [AIMessage]} —— deepagents 从后往前找最后一条非空
    AIMessage 当 task 的返回值，形状不对它会直接 raise ValueError。"""
    r = _with_failure_fallback(RunnableLambda(_raise(RuntimeError("上游 500"))), LABEL)
    out = await r.ainvoke({"messages": []})

    assert "messages" in out
    last = out["messages"][-1]
    assert isinstance(last, AIMessage)
    assert last.text, "内容不能为空，否则 deepagents 会继续往前找、拿到别的东西"
    assert LABEL in last.text, "supervisor 要知道是谁没干成"
    assert "上游 500" not in last.text, "原始异常细节不喂给模型（栈 / 路径 / SQL 同理）"


async def test_步数用完给的是可操作的建议():
    """撞上限和一般失败该给不同的话：前者拆小任务再派，后者换人。"""
    r = _with_failure_fallback(RunnableLambda(_raise(GraphRecursionError())), LABEL)
    out = await r.ainvoke({"messages": []})

    text = out["messages"][-1].text
    assert "步数" in text
    assert "拆小" in text


async def test_一般失败与步数用完文案不同():
    r_step = _with_failure_fallback(RunnableLambda(_raise(GraphRecursionError())), LABEL)
    r_other = _with_failure_fallback(RunnableLambda(_raise(RuntimeError("boom"))), LABEL)

    step = (await r_step.ainvoke({"messages": []}))["messages"][-1].text
    other = (await r_other.ainvoke({"messages": []}))["messages"][-1].text
    assert step != other


async def test_用户中断不被兜住():
    """CancelledError 继承 BaseException，而 exceptions_to_handle 默认只收
    Exception —— 掐断时子 agent 该正常取消，不能被歪曲成「执行出错了」。"""
    r = _with_failure_fallback(RunnableLambda(_raise(asyncio.CancelledError())), LABEL)

    with pytest.raises(asyncio.CancelledError):
        await r.ainvoke({"messages": []})
