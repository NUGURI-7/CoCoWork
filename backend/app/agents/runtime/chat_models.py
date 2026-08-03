"""OpenAI 兼容端点的推理内容支持 —— 补 langchain-openai 刻意不做的那半。

`ChatOpenAI` 的 docstring 明说：只对齐 OpenAI 官方规范，第三方加的非标字段
（`reasoning_content` / `reasoning_details`）**不解析也不保留**，并建议改用
provider 专用包。但 DeepSeek / 通义 QwQ / SiliconFlow 上的 R1 蒸馏全都走
OpenAI 兼容协议、全都吐 `reasoning_content`，而官方只给了 `ChatDeepSeek`
一家 —— 与其一家引一个包，不如在兼容层补这一笔，一个子类通吃。

两件事缺一不可：
1. 解析：响应 delta 里的 reasoning_content → additional_kwargs（思考块靠它出现）
2. 回传：带 tool_calls 的 assistant 消息必须原样带回 reasoning_content

第 2 件是 DeepSeek 的硬性要求（缺了报 400），且只在**同一轮的工具调用过程中**
成立；跨轮历史不回传（那是 ViewContextAssembler 的事，本层不碰）。
只做前一件会比现在更糟：现在全程没有 reasoning_content 所以相安无事，
一旦解析出来却不回传，凡是调工具的那轮都会开始 400。
"""

from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI

# 上游字段名两种写法都见过：DeepSeek / 通义用 reasoning_content，
# 部分网关（OpenRouter 等）转发时写成 reasoning。
_REASONING_KEYS = ("reasoning_content", "reasoning")

# 落进 additional_kwargs 的键 —— adapter._extract_reasoning 读的就是它
_REASONING_KWARG = "reasoning_content"


def _pick_reasoning(delta: dict[str, Any]) -> str | None:
    """从一个 delta 里取推理增量，取不到返回 None。"""
    for key in _REASONING_KEYS:
        value = delta.get(key)
        if isinstance(value, str) and value:
            return value
    return None


class ReasoningChatOpenAI(ChatOpenAI):
    """ChatOpenAI + 推理内容的解析与回传。

    只覆盖两个钩子，不复制父类任何内部实现 —— langchain-openai 升级时
    受影响面仅限这两个方法的签名。
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """流式：父类转完之后，把它丢掉的 reasoning 增量补回 additional_kwargs。"""
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info,
        )
        if generation_chunk is None:
            return None

        # choices 的两种位置与父类保持一致（后者来自 beta.chat.completions.stream）
        choices = (
            chunk.get("choices")
            or chunk.get("chunk", {}).get("choices")
            or []
        )
        if not choices:
            return generation_chunk

        delta = choices[0].get("delta") or {}
        reasoning = _pick_reasoning(delta)
        if reasoning is not None:
            generation_chunk.message.additional_kwargs[_REASONING_KWARG] = reasoning
        return generation_chunk

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """请求：把带 tool_calls 的 assistant 消息的 reasoning_content 塞回 payload。

        父类序列化时会丢掉 additional_kwargs 里的非标字段，所以先从原始
        messages 记下位置，等父类转完再按下标填回去。下标对应之外再校验一次
        role / tool_calls，避免父类将来改变消息数量时填错位置。
        """
        messages = self._convert_input(input_).to_messages()
        reasoning_by_index = {
            index: reasoning
            for index, message in enumerate(messages)
            if isinstance(message, AIMessage)
            and (message.tool_calls or message.invalid_tool_calls)
            and (reasoning := message.additional_kwargs.get(_REASONING_KWARG))
        }

        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if not reasoning_by_index:
            return payload

        for index, message in enumerate(payload.get("messages", [])):
            reasoning = reasoning_by_index.get(index)
            if (
                reasoning
                and message.get("role") == "assistant"
                and message.get("tool_calls")
            ):
                message[_REASONING_KWARG] = reasoning
        return payload


# 显式关闭档 —— 与"没配"区分开：没配是不干预，off 是主动要求别思考
_REASONING_OFF = "off"


def apply_reasoning_params(params: dict[str, Any]) -> dict[str, Any]:
    """把思考档位翻成上游要的参数（原地改并返回同一个 dict）。

    只认 DeepSeek 一家的方言（顶层 reasoning_effort + extra_body.thinking）——
    接第二家推理模型时再谈抽象，现在多一层只是空转。

    `extra_body` 用 setdefault 取：OpenAIParamAdapter 随后也会往同一个 dict
    塞 max_tokens，两者合并而非互相覆盖。

    思考模式下 temperature / top_p / 两个 penalty 按 DeepSeek 文档是"不支持"的，
    但实测传了不报错、只是被忽略，故不做剥离 —— 剥了反而让用户在 UI 里设的值
    无声消失。
    """
    effort = params.pop("reasoning_effort", None)
    if effort is None:
        return params

    is_off = effort == _REASONING_OFF
    params.setdefault("extra_body", {})["thinking"] = {
        "type": "disabled" if is_off else "enabled",
    }
    if not is_off:
        params["reasoning_effort"] = effort
    return params
