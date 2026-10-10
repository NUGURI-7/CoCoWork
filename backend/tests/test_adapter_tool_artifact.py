"""adapter 转发工具 artifact 的单测 —— 合成事件流,零 LLM 调用。

只有 ClientArtifact 才随 tool_result 事件往前端 / 落库走;
MCP 适配器那类普通 dict artifact 必须被丢掉(无大小上限、前端用不上)。
"""
from uuid import uuid4

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.events import EventType
from app.tools.knowledge_retrieval import KnowledgeHitsArtifact


async def _stream(events: list[dict]):
    for ev in events:
        yield ev


def _tool_events(artifact) -> list[dict]:
    """模型发起一次工具调用 → 工具执行完带回 artifact。"""
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{"name": "knowledge_x", "args": '{"query": "q"}', "id": "call_1", "index": 0}],
    )
    msg = ToolMessage(content="命中正文", tool_call_id="call_1", artifact=artifact)
    return [
        {"event": "on_chat_model_start", "metadata": {}, "data": {}},
        {"event": "on_chat_model_stream", "metadata": {}, "data": {"chunk": chunk}},
        {"event": "on_chat_model_end", "metadata": {}, "data": {}},
        {"event": "on_tool_end", "metadata": {}, "data": {"output": msg}},
    ]


async def _tool_result(artifact) -> dict:
    out = [e async for e in adapt_chat_stream(_stream(_tool_events(artifact)))]
    results = [p for t, p in out if t == EventType.TOOL_RESULT]
    assert len(results) == 1
    return results[0]


async def test_client_artifact_转成json转发():
    pid = uuid4()
    payload = await _tool_result(KnowledgeHitsArtifact(paragraph_ids=[pid]))
    assert payload["artifact"] == {"kind": "knowledge_hits", "paragraph_ids": [str(pid)]}
    assert payload["result_data"] == "命中正文"


async def test_其他来源的artifact被丢弃():
    payload = await _tool_result({"structured_content": {"rows": list(range(1000))}})
    assert payload["artifact"] is None


async def test_无artifact时为None():
    payload = await _tool_result(None)
    assert payload["artifact"] is None
