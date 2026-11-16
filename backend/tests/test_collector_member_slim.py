"""成员过程块落库瘦身：完整结果不存、入参字段截短；supervisor 自己的块原样。"""

import json

from app.agents.runtime.collector import _MEMBER_ARG_KEEP_CHARS, MessageCollector, _slim_member_block


def _tool(subagent: str | None, args: str, result="完整结果" * 100) -> dict:
    block = {"type": "tool_use", "id": "t1", "name": "write_file", "partial_json": args,
             "result_summary": "Updated file", "result_data": result, "status": "success"}
    if subagent:
        block["subagent"] = subagent
    return block


def test_成员块去掉结果并截短入参():
    args = json.dumps({"file_path": "/workspace/a.svg", "content": "<svg>" + "x" * 5000})
    slim = _slim_member_block(_tool("member_1", args))

    assert slim["result_data"] is None
    assert slim["result_summary"] == "Updated file"
    parsed = json.loads(slim["partial_json"])
    assert parsed["file_path"] == "/workspace/a.svg"
    assert len(parsed["content"]) == _MEMBER_ARG_KEEP_CHARS


def test_supervisor_自己的块原样不动():
    block = _tool(None, json.dumps({"content": "y" * 5000}))
    assert _slim_member_block(block) is block


def test_入参半截时清空不报错():
    slim = _slim_member_block(_tool("member_1", '{"command": "ls -'))
    assert slim["partial_json"] == ""
    assert slim["result_data"] is None


def test_blocks_出桶瘦身但不改原始记录():
    c = MessageCollector()
    c._blocks[0] = {"type": "text", "text": "好的"}
    c._blocks[1] = _tool("member_1", json.dumps({"command": "z" * 1000}))

    out = c.blocks
    assert out[0] == {"type": "text", "text": "好的"}
    assert out[1]["result_data"] is None
    assert c._blocks[1]["result_data"] is not None
