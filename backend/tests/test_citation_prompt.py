"""引用规则什么时候进开场说明 —— 零 LLM 调用、零数据库。

锁两件事：
- 判断依据是「手上真有知识库工具」，不是配置里填没填库；
- 被派活的成员拿到规则时，要把这个事实告诉 supervisor（它据此补「原样保留记号」）。
"""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.schemas.agent import AgentConfig
from app.tools.knowledge_retrieval import (
    CITATION_RULES,
    KnowledgeRetrievalTool,
    citation_rules_for,
)


def _kb_tool() -> KnowledgeRetrievalTool:
    return KnowledgeRetrievalTool.model_construct(
        name="knowledge_x", description="d", display_name="知识库《手册》",
        kb_id=uuid4(), user=None,
    )


def _plain_tool():
    from app.tools import resolve_tools
    return resolve_tools(["calculator"])[0]


def test_有知识库工具才给规则():
    assert citation_rules_for([_plain_tool(), _kb_tool()]) == CITATION_RULES


def test_没有知识库工具不给规则():
    assert citation_rules_for([_plain_tool()]) is None
    assert citation_rules_for([]) is None


async def _build_member(tools: list):
    """装配一个派活成员，返回 (三元组, 喂给 create_agent 的 system_prompt)。"""
    from app.agents.workspace import workspace as ws

    captured = {}

    def fake_create_agent(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return SimpleNamespace()

    async def fake_assemble(cfg, user):
        return list(tools)

    async def fake_profile(cfg, user):
        return "无"

    member = SimpleNamespace(id=uuid4(), agent=SimpleNamespace(name="资料员", description=""))
    with (
        patch.object(ws, "assemble_tools", fake_assemble),
        patch.object(ws, "build_capability_profile", fake_profile),
        patch.object(ws, "create_agent", fake_create_agent),
        patch.object(ws, "_base_middleware", lambda model: []),
        patch.object(ws, "_with_failure_fallback", lambda r, *_args, **_kw: r),
        patch.object(ws, "_with_member_step_limit", lambda r, *_args, **_kw: r),
    ):
        result = await ws._member_to_subagent(
            member, AgentConfig(), user=None, fallback_model=None, mount=None,
            memory_section="## 工作区记忆\n每周五交周报",
        )
    return result, captured["system_prompt"]


async def test_挂了知识库的成员拿到规则并告知supervisor():
    (_, _, cites), prompt = await _build_member([_kb_tool()])

    assert cites is True
    assert CITATION_RULES in prompt
    # 记忆仍垫在最后一节
    assert prompt.index(CITATION_RULES) < prompt.index("## 工作区记忆")


async def test_没挂知识库的成员不拿规则():
    (_, _, cites), prompt = await _build_member([_plain_tool()])

    assert cites is False
    assert CITATION_RULES not in prompt
