"""流式事件收集器 —— sink 的标准消费者。

runner 边流边把 (EventType, payload) 喂进来（`run_chat_stream(sink=collector.feed)`），
流完后调用方从桶里拿完整消息：message_id + blocks + 有没有出过错。

只攒不判：done / stopped 由调用方控制流位置判定（自然走完 = done、
中途被掐 = stopped），桶只记录"收到过 error 事件"这个事实。

不 import 任何业务模块（workspace / agent CRUD）—— 落库 / audit / replay
等任何要"留一份完整消息"的场景都能复用。
"""

from typing import Any

from app.agents.runtime.events import EventType


def _token_count(value: Any) -> int:
    """token 数取值：非 int / 负数 / bool 一律当 0。

    跑在 SSE 热路径上，宁可少算一次，也不能因为 provider 回了个怪值就炸。
    （bool 是 int 的子类，不排掉的话 True 会被当成 1 累进去。）
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value if value > 0 else 0


class MessageCollector:
    """攒一条流式 assistant 消息。

    blocks 落库形态 = SSE 事件攒平（snake_case、字段名与 SSE payload 一致），
    不带前端 UI 状态（collapsed / active）—— DB 存事实，UI 状态是前端的事。
    """

    def __init__(self) -> None:
        self.message_id: str = ""
        self.saw_error: bool = False
        self.error_message: str = ""
        # 本轮上下文规模（主道最后一次模型调用的 input_tokens）——落 Conversation
        # 而非 Message，是层 B 下一轮判断该不该压缩的依据
        self.context_tokens: int = 0
        # 本轮消耗明细：delegate_id → 两个计数（None = supervisor 主道）。
        # 跟 context_tokens 是两笔账：那笔只认主道、取最后一次（层 B 判据），
        # 这笔全道累加（总消耗）。
        self._usage: dict[str | None, dict[str, int]] = {}
        # index → 块。delta / tool_result 事件都带 index 反查目标块，
        # dict 寻址 O(1)；出桶时按 index 升序还原成 list。
        self._blocks: dict[int, dict[str, Any]] = {}

    @property
    def blocks(self) -> list[dict[str, Any]]:
        """按 index 升序的完整块列表 —— 落库 content 的最终形态。"""
        return [self._blocks[i] for i in sorted(self._blocks)]

    @property
    def prompt_tokens(self) -> int:
        """本轮全部模型调用的输入合计（含子 agent）。"""
        return sum(row["prompt_tokens"] for row in self._usage.values())

    @property
    def completion_tokens(self) -> int:
        """本轮全部模型调用的输出合计（含子 agent）。"""
        return sum(row["completion_tokens"] for row in self._usage.values())

    @property
    def usage_rows(self) -> list[dict[str, Any]]:
        """消耗明细，一行 = 一个计费单元：supervisor 或某一次派活。

        按首次出现排序（dict 保插入序），supervisor 天然在最前 —— 它得先调一次
        模型才谈得上派活。行里只有 delegate_id 和两个数：成员名 / 任务描述由前端
        拿 delegate_id 去 content 里那个 task 块自取，同一份数据不存两遍。
        """
        return [
            {"delegate_id": delegate_id, **counts}
            for delegate_id, counts in self._usage.items()
        ]

    @property
    def usage_summary(self) -> dict[str, Any]:
        """终止帧 / 落库共用的一份 —— 三个键跟 messages 表的三列一一对应。

        SSE 发的和存进库的是同一份数字，前端刷新前后看到的必然一致。
        """
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "token_usage": self.usage_rows,
        }

    def feed(self, event: EventType, payload: dict[str, Any]) -> None:
        """sink 入口 —— runner 每产一个事件喂一次。

        跑在 SSE hot path 上，必须轻、必须不抛（runner 的 _feed_sink
        有兜底，但那是保险不是许可）。未知事件静默跳过 —— 协议将来
        加新事件类型，旧桶不炸。
        """
        match event:
            case EventType.MESSAGE_START:
                self.message_id = payload.get("id", "")
            case EventType.CONTENT_BLOCK_START:
                self._open_block(payload)
            case EventType.CONTENT_BLOCK_DELTA:
                self._append_delta(payload)
            case EventType.TOOL_USE_START:
                self._open_tool_block(payload)
            case EventType.TOOL_USE_DELTA:
                self._append_tool_json(payload)
            case EventType.TOOL_RESULT:
                self._fill_tool_result(payload)
            case EventType.MESSAGE_DELTA:
                self._absorb_usage(payload)
            case EventType.ERROR:
                self.saw_error = True
                self.error_message = payload.get("message", "")
            case _:
                # CONTENT_BLOCK_STOP / TOOL_USE_STOP / MESSAGE_STOP —— 桶无动作：
                # 块的"完整性"由内容本身体现，不需要关块标记。
                pass

    def _open_block(self, payload: dict[str, Any]) -> None:
        """content_block_start → 开 text / thinking 块，内容先置空串。"""
        index = payload.get("index")
        block_type = payload.get("type", "")
        if index is None or not block_type:
            return
        block: dict[str, Any] = {"type": block_type, block_type: ""}
        subagent = payload.get("subagent")
        if subagent:
            block["subagent"] = subagent
        delegate_id = payload.get("delegate_id")
        if delegate_id:
            block["delegate_id"] = delegate_id
        self._blocks[index] = block

    def _append_delta(self, payload: dict[str, Any]) -> None:
        """content_block_delta → 按 index 找块、追加内容增量。"""
        index = payload.get("index")
        block = self._blocks.get(index)
        if block is None:
            return
        key = block["type"]
        delta = payload.get(key)
        if isinstance(delta, str):
            block[key] += delta

    def _open_tool_block(self, payload: dict[str, Any]) -> None:
        """tool_use_start → 开 tool 块；结果字段占位，等 tool_result 回填。"""
        index = payload.get("index")
        if index is None:
            return

        block: dict[str, Any] = {
            "type": "tool_use",
            "id": payload.get("id", ""),
            "name": payload.get("name", ""),
            "input_preview": payload.get("input_preview", ""),
            "partial_json": "",
            "result_summary": None,
            "result_data": None,
            "status": None,
        }
        subagent = payload.get("subagent")
        if subagent:
            block["subagent"] = subagent
        delegate_id = payload.get("delegate_id")
        if delegate_id:
            block["delegate_id"] = delegate_id
        self._blocks[index] = block

    def _append_tool_json(self, payload: dict[str, Any]) -> None:
        """tool_use_delta → 追加 partial JSON 增量（攒齐即完整入参串）。"""
        index = payload.get("index")
        block = self._blocks.get(index)
        if block is None:
            return
        delta = payload.get("partial_json")
        if isinstance(delta, str):
            block["partial_json"] += delta

    def _fill_tool_result(self, payload: dict[str, Any]) -> None:
        """tool_result → 回填结果三件套 + 结局 status。"""
        index = payload.get("index")
        block = self._blocks.get(index)
        if block is None:
            return
        block["status"] = payload.get("status")
        block["result_summary"] = payload.get("result_summary")
        block["result_data"] = payload.get("result_data")

    def _absorb_usage(self, payload: dict[str, Any]) -> None:
        """message_delta → 分流进两笔互不相干的账。

        adapter 主 / 子道都发 usage，子道那帧带 delegate_id 戳 —— **有没有这个
        字段就是分流判据**，不需要额外的协议字段。
        """
        usage = payload.get("usage") or {}
        delegate_id = payload.get("delegate_id")
        self._accumulate_usage(delegate_id, usage)
        if delegate_id is None:
            self._track_context_size(usage)

    def _accumulate_usage(self, delegate_id: str | None, usage: dict[str, Any]) -> None:
        """总消耗：每次模型调用报一份，往所属行里累加。

        累加而非去重 —— 模型无状态，同一段历史每轮都得重发一次，它就是真的被读了
        那么多遍（dify / letta 同口径）。这个数因此**不等于**「上下文有多长」，
        后者是 context_tokens 那笔账。

        行的单位是「一次派活」而非「一个成员」：delegate_id 由 langgraph 每次 task
        派发独立生成，同名成员被并发派两次也是两行 —— 那本就是两件事。supervisor
        没有这种天然分界，主道全部调用合并进 None 这一行。
        """
        prompt = _token_count(usage.get("input_tokens"))
        completion = _token_count(usage.get("output_tokens"))
        if prompt == 0 and completion == 0:
            return
        row = self._usage.setdefault(
            delegate_id, {"prompt_tokens": 0, "completion_tokens": 0},
        )
        row["prompt_tokens"] += prompt
        row["completion_tokens"] += completion

    def _track_context_size(self, usage: dict[str, Any]) -> None:
        """本轮上下文规模（后来者覆盖前者 = 取最后一次）—— 层 B 下轮的压缩判据。

        一轮回复里主道会调好几次模型，每次各报一份 usage。取**最后一次**的
        input_tokens：它含本轮全部工具往返，而工具结果是要全量进下一轮历史的
        （见 docs/design/history-replay-v1.md），所以它就是下轮进场历史的量。

        **这个选择绑死在回放协议上**：若哪天改回「工具结果不进历史、只留一行
        痕迹」，最后一次会虚高十几倍，届时要改成只认第一次（加个「已有值就
        return」即可）。

        只接主道（调用方已按 delegate_id 拦过）—— 子 agent 的上下文是本轮临时的、
        run 完即弃（归层 A 管），跟对话历史规模无关，混进来就把判据搞乱了。
        """
        tokens = _token_count(usage.get("input_tokens"))
        if tokens > 0:
            self.context_tokens = tokens
