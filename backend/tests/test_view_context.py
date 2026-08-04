"""ViewContextAssembler 的视角化 + 回放形状单测 —— 纯内存，零 DB 零 LLM。

这一层为什么值得单测：它的产物是**直接喂给 API 的消息列表**，形状错了不是
结果不准，是整轮请求当场报错（tool_call 没有配对结果）或者模型开始编造
（事实被压平进它自己能写的通道）。两类 bug 都不会在代码里显形。

三组断言，性质不同：

1. **配对不变式** —— 每个 tool_call 必须紧跟一条同 id 的结果。这是 API 的硬
   约束，也是「改回原生形状」这一刀唯一会把生产打挂的地方。库里 12% 的块
   是没结局的（用户中途点停止），所以中断那条尤其要测。
2. **视角分叉** —— 同一条历史，自己看是 AIMessage+ToolMessage、别人看是一条
   带 <msg from> 的 HumanMessage。写反了不报错，只是模型开始把别人的调用
   当成自己的。
3. **回归界碑** —— 跳过 thinking / 跳过 subagent 块 / 别人的结果要带上。
   这几条是绕了好几轮定的决策，测试在这里是防日后重构顺手改掉。
"""

from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.workspace.view_context_assembler import (
    ViewContextAssembler,
    Viewer,
    split_at_cursor,
)
from app.core.identifiers import short_id
from app.models import Message, MessageRole, SandboxArtifact, SenderKind
from app.tools.base import MAX_TOOL_OUTPUT_CHARS

MEMBER_A = UUID("019f0d9b-1111-7000-8000-000000000001")
MEMBER_B = UUID("019f0d9b-2222-7000-8000-000000000002")
NAMES = {MEMBER_A: "小A", MEMBER_B: "小B"}

SUPERVISOR_VIEW = Viewer(sender_kind=SenderKind.SUPERVISOR)
MEMBER_A_VIEW = Viewer(sender_kind=SenderKind.MEMBER, member_id=MEMBER_A)


def msg(
        blocks: list[dict],
        kind: SenderKind = SenderKind.SUPERVISOR,
        member_id: UUID | None = None,
        mid: UUID | None = None,
) -> Message:
    """造一条历史消息。sender_member_id 只能构造后赋值 —— Tortoise 的 FK
    描述符要连上库才建得起来，而这层测试刻意不连库。"""
    m = Message(
        id=mid or uuid4(),
        role=MessageRole.USER if kind == SenderKind.USER else MessageRole.ASSISTANT,
        sender_kind=kind,
        content=blocks,
    )
    m.sender_member_id = member_id
    return m


def tool(name: str, *, cid: str = "c1", args: str = "{}", result=None, status="success") -> dict:
    """造一个 tool_use 块。result=None + status=None 即「中断，没有结局」。"""
    return {
        "type": "tool_use", "id": cid, "name": name,
        "partial_json": args, "result_data": result, "status": status,
    }


async def assemble(past: list[Message], viewer: Viewer, artifacts=None, summary=None):
    return await ViewContextAssembler().build(
        past, viewer, NAMES, artifacts or {}, summary,
    )


async def build(past: list[Message], viewer: Viewer, artifacts=None):
    """只要消息列表 —— 绝大多数用例不关心 truncated 那个标志。"""
    return (await assemble(past, viewer, artifacts)).messages


def assert_paired(out: list) -> None:
    """配对不变式：每条 tool_call 后面必须紧跟同 id 的结果，不多不少不错位。

    直接照 API 的要求写：孤儿 tool_call 会让整轮请求 400，而这是本刀最容易
    翻车的地方（压平方案当初白捡了这个便宜）。
    """
    expected: list[str] = []
    for m in out:
        if isinstance(m, AIMessage):
            assert not expected, f"上一批 tool_call 的结果还没给全就开了新消息：{expected}"
            expected = [c["id"] for c in m.tool_calls]
        elif isinstance(m, ToolMessage):
            assert expected, "冒出一条没有对应 tool_call 的结果"
            assert m.tool_call_id == expected.pop(0), "结果顺序与 tool_call 不一致"
    assert not expected, f"有 tool_call 没拿到结果：{expected}"


# ============ 配对不变式 ============


async def test_own_tool_call_gets_a_paired_result():
    past = [msg([{"type": "text", "text": "查一下"}, tool("maps_geo", result="北京")])]
    out = await build(past, SUPERVISOR_VIEW)

    assert_paired(out)
    assert isinstance(out[1], ToolMessage) and out[1].content == "北京"


async def test_interrupted_call_still_gets_a_result():
    """用户中途点停止 → 块没有结局。**照样要给一条结果**，否则 API 报错。

    库里这类块占 12%，不是边角情况。
    """
    past = [msg([tool("maps_geo", result=None, status=None)])]
    out = await build(past, SUPERVISOR_VIEW)

    assert_paired(out)
    assert out[1].status == "error"
    assert "中断" in out[1].content


async def test_blocks_without_id_get_unique_fallback_ids():
    """脏 jsonb 没有 id 时兜底造一个，且同一条消息里两个块不能撞。

    撞了就是两条结果配到同一个调用上 —— 比缺结果更难查。
    """
    mid = UUID("019fb2af-c9bb-7551-a117-b3eb4060dff1")
    past = [msg([tool("a", cid="", result="1"), tool("b", cid="", result="2")], mid=mid)]
    out = await build(past, SUPERVISOR_VIEW)

    assert_paired(out)
    # 用 short_id 现算而不是写死字面量：短标识的取法改过一次（前 8 位 → 后 8 位，
    # 见 core.identifiers），写死的断言当时全体过期
    assert [c["id"] for c in out[0].tool_calls] == [
        f"{short_id(mid)}-0", f"{short_id(mid)}-1"
    ]


# ============ 视角分叉：同一条历史，两种画法 ============


async def test_own_message_keeps_the_native_tool_shape():
    """自己那条 → 原生 AIMessage(tool_calls) + ToolMessage，入参原样还原。

    这是治「凭空编造派活」的钉子：role="tool" 是平台写的字段，模型伪造不了。
    """
    past = [msg([tool("maps_geo", args='{"city":"北京"}', result="纬度…")],
                SenderKind.MEMBER, MEMBER_A)]
    out = await build(past, MEMBER_A_VIEW)

    assert out[0].tool_calls == [
        {"name": "maps_geo", "args": {"city": "北京"}, "id": "c1", "type": "tool_call"}
    ]


async def test_others_message_becomes_one_narrated_human_message():
    """别人那条 → 一条 HumanMessage。**不能给结构** —— 结构化的语义是
    「你调用了它」，而管家根本没调过，甚至可能没挂那个工具。"""
    past = [msg([tool("maps_geo", result="纬度…")], SenderKind.MEMBER, MEMBER_A)]
    out = await build(past, SUPERVISOR_VIEW)

    assert len(out) == 1 and isinstance(out[0], HumanMessage)
    assert f'<msg from="小A#{short_id(MEMBER_A)}">' in out[0].content


async def test_others_tool_result_is_carried_over():
    """别人的工具结果必须进历史 —— 丢了就答不出「刚才查到什么」。"""
    past = [msg([tool("maps_weather", result="北京 晴 12℃")], SenderKind.MEMBER, MEMBER_A)]
    out = await build(past, SUPERVISOR_VIEW)

    assert "北京 晴 12℃" in out[0].content


async def test_another_member_is_not_me():
    """同是 member 但不是同一个人 → 走「别人」那档。

    _is_me 只比 sender_kind 就会让所有成员共用一个身份，谁都以为别人的话是
    自己说的。
    """
    past = [msg([{"type": "text", "text": "我是小B"}], SenderKind.MEMBER, MEMBER_B)]
    out = await build(past, MEMBER_A_VIEW)

    assert isinstance(out[0], HumanMessage)
    assert f'<msg from="小B#{short_id(MEMBER_B)}">' in out[0].content
    # 两个成员的 UUID 前 8 位故意相同 —— 短标识若取前缀，这一断言会连同「谁是谁」
    # 一起失守（f6705ae 修的正是这个）
    assert short_id(MEMBER_A) != short_id(MEMBER_B)


async def test_user_speech_is_labelled():
    """历史里 user 也具名 —— 不留「负空间」，否则成员会把 user 认成别的成员。"""
    past = [msg([{"type": "text", "text": "在吗"}], SenderKind.USER)]
    out = await build(past, SUPERVISOR_VIEW)

    assert out[0].content == '<msg from="User">在吗</msg>'


# ============ 切分与跳过 ============


async def test_text_after_tool_starts_a_new_call():
    """文字 → 工具 → 文字 本就是两次模型调用，还原成两条 AIMessage。"""
    past = [msg([
        {"type": "text", "text": "先查"},
        tool("maps_geo", result="北京"),
        {"type": "text", "text": "查到了"},
    ])]
    out = await build(past, SUPERVISOR_VIEW)

    assert [m.content for m in out if isinstance(m, AIMessage)] == ["先查", "查到了"]
    assert_paired(out)


async def test_subagent_blocks_are_skipped():
    """成员的执行过程整体跳过 —— 交付内容已在 task 块的结果里。"""
    past = [msg([
        tool("task", cid="t1", result="图画好了"),
        {**tool("write_file", cid="w1", result="ok"), "subagent": "小A"},
    ])]
    out = await build(past, SUPERVISOR_VIEW)

    assert [c["name"] for c in out[0].tool_calls] == ["task"]
    assert_paired(out)


async def test_thinking_is_not_replayed():
    """思考过程不回放 —— DeepSeek 明令禁止回传，Anthropic 侧自动剥离。"""
    past = [msg([{"type": "thinking", "thinking": "让我想想"},
                 {"type": "text", "text": "结论"}])]
    out = await build(past, SUPERVISOR_VIEW)

    assert [m.content for m in out] == ["结论"]


# ============ 超长结果封顶 ============

OVERSIZED = "x" * (MAX_TOOL_OUTPUT_CHARS + 1)


async def test_oversized_result_is_capped_with_a_pointer():
    """超限的结果只留开头一截 + 取回指引 —— 否则它会一直占着窗口。"""
    past = [msg([tool("maps_direction", cid="c1", result=OVERSIZED)])]
    out = await build(past, SUPERVISOR_VIEW)

    body = out[1].content
    assert len(body) < MAX_TOOL_OUTPUT_CHARS
    assert f"完整 {len(OVERSIZED)} 字符" in body
    assert 'read_tool_result(tool_use_id="c1")' in body


async def test_oversized_result_is_capped_for_others_too():
    """别人那档同样封顶 —— 两条渲染路径共用一个判据。"""
    past = [msg([tool("maps_direction", cid="c1", result=OVERSIZED)],
                SenderKind.MEMBER, MEMBER_A)]
    out = await build(past, SUPERVISOR_VIEW)

    assert 'read_tool_result(tool_use_id="c1")' in out[0].content


async def test_capped_result_without_id_gets_no_pointer():
    """脏数据没有库里那个 id → 取不回来，就别教模型去调一个必然失败的调用。"""
    past = [msg([tool("x", cid="", result=OVERSIZED)])]
    out = await build(past, SUPERVISOR_VIEW)

    assert "已截断" in out[1].content
    assert "read_tool_result" not in out[1].content


async def test_truncated_flag_follows_the_history():
    """标志与标记必须同源 —— 装配方靠它决定挂不挂 read_tool_result。

    带 subagent 戳的块不回放，因此再大也不算数；不然会挂了工具却没有任何
    标记指向它。
    """
    small = [msg([tool("a", result="短")])]
    big = [msg([tool("a", result=OVERSIZED)])]
    stamped = [msg([{**tool("a", result=OVERSIZED), "subagent": "小A"}])]

    assert (await assemble(small, SUPERVISOR_VIEW)).truncated is False
    assert (await assemble(big, SUPERVISOR_VIEW)).truncated is True
    assert (await assemble(stamped, SUPERVISOR_VIEW)).truncated is False


# ============ 产物标注 ============


async def test_artifacts_note_is_its_own_system_message():
    """产物清单是**独立一条** <msg from="System">，不并进模型自己的发言。

    并进去实测复现过：模型看见自己上次发言末尾挂着这行，下次就照抄一行出来
    （大小还是猜的），那串内部标记被前端当正文渲染给了用户。独立一条之后它
    抄不了 —— 它的输出永远是 assistant 角色，变不成这条 user 角色的消息。

    3598 字节渲染成 `4KB`（human_size 在 KB 档取整）—— 顺带钉住这个口径：
    它是给模型判断「这文件大不大」用的，不是给人核对字节数的。
    """
    mid = uuid4()
    art = SandboxArtifact(filename="chart.svg", size=3598)
    past = [msg([{"type": "text", "text": "画好了"}], mid=mid)]
    out = await build(past, SUPERVISOR_VIEW, {mid: [art]})

    assert [type(m).__name__ for m in out] == ["AIMessage", "HumanMessage"]
    assert out[0].content == "画好了"  # 自己的发言里一个字的标注都不掺
    assert out[1].content == '<msg from="System"><artifacts>chart.svg (4KB)</artifacts></msg>'


async def test_artifacts_of_others_also_go_to_a_system_message():
    """成员产出的文件同样挪出来 —— 那不是小A说的话，是系统记的事实。"""
    mid = uuid4()
    art = SandboxArtifact(filename="chart.svg", size=2048)
    past = [msg([{"type": "text", "text": "画好了"}], SenderKind.MEMBER, MEMBER_A, mid=mid)]
    out = await build(past, SUPERVISOR_VIEW, {mid: [art]})

    assert out[0].content == f'<msg from="小A#{short_id(MEMBER_A)}">画好了</msg>'
    assert out[1].content == '<msg from="System"><artifacts>chart.svg (2KB)</artifacts></msg>'


# ---------------------------------------------------------------- 封存游标

def test_游标为空时全部未覆盖():
    past = [msg([{"type": "text", "text": "x"}]) for _ in range(5)]
    covered, uncovered = split_at_cursor(past, None)

    assert covered == []
    assert uncovered == past


def test_游标把历史切成两半():
    """覆盖到第 2 条为止 → 前三条已封存，第 3 条往后还要原样回放。"""
    past = [msg([{"type": "text", "text": "x"}]) for _ in range(5)]
    covered, uncovered = split_at_cursor(past, past[2].id)

    assert covered == past[:3]     # 游标那条自己也算已覆盖
    assert uncovered == past[3:]
    assert not set(id(m) for m in covered) & set(id(m) for m in uncovered)


def test_覆盖到最后一条时没有可回放的():
    past = [msg([{"type": "text", "text": "x"}]) for _ in range(5)]
    covered, uncovered = split_at_cursor(past, past[-1].id)

    assert covered == past
    assert uncovered == []


def test_游标找不到时按未覆盖处理():
    """重放一遍全量是浪费，漏掉一整段是永久失忆 —— 两害相权取轻。"""
    past = [msg([{"type": "text", "text": "x"}]) for _ in range(5)]
    covered, uncovered = split_at_cursor(past, uuid4())

    assert covered == []
    assert uncovered == past
