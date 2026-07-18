"""一次性探测脚本：验证 OpenAI 兼容 provider 的流式 usage / prompt cache 上报。

回答两个问题（Compress 片的数据源前提）：
1. 流式响应里返不返 usage（input_tokens / output_tokens）？
   —— langchain-openai 对自定义 base_url 默认关 stream_usage，这里显式打开。
2. 报不报 prompt cache 命中（input_token_details.cache_read）？
   —— 同一长前缀连发两次，看第二次 cache_read 是否 > 0。

用法（backend/ 目录下）：
    uv run python scripts/probe_stream_usage.py            # 列出可用 chat 模型
    uv run python scripts/probe_stream_usage.py <序号>      # 用第 N 个模型探测
"""

import asyncio
import sys

from langchain_core.messages import HumanMessage, SystemMessage
from tortoise import Tortoise

from app.agents.runtime.runner import build_chat_model
from app.db.postgresql import TORTOISE_CONFIG
from app.models import AIModel
from app.schemas.agent.config_schema import ModelSlot

# 长前缀：重复段落凑到 ~4000 字（> 各家自动缓存的最小前缀门槛，通常 1024 token）
_PREFIX_UNIT = (
    "你是一个严谨的助手。以下是背景资料第 {i} 条：多智能体系统的上下文工程包含"
    "压缩、选择、写入、隔离四个方面，其中压缩关注如何在有限的上下文窗口内保留"
    "关键信息，隔离关注不同智能体之间的视角边界与状态边界。"
)
_LONG_PREFIX = "".join(_PREFIX_UNIT.format(i=i) for i in range(40))


def _dump_usage(tag: str, usage) -> None:
    print(f"  [{tag}] usage_metadata = {usage!r}")


async def _stream_once(model, messages, tag: str):
    """跑一次流式调用，扫描所有 chunk 找 usage_metadata，返回找到的那份。"""
    found = None
    n_chunks = 0
    async for chunk in model.astream(messages):
        n_chunks += 1
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            found = usage
    print(f"  [{tag}] 共 {n_chunks} 个 chunk，usage {'✅ 有' if found else '❌ 无'}")
    _dump_usage(tag, found)
    return found


async def main() -> None:
    await Tortoise.init(config=TORTOISE_CONFIG)
    try:
        models = (
            await AIModel.filter(model_type="chat", is_enabled=True)
            .prefetch_related("provider")
            .order_by("created_at")
        )
        if not models:
            print("DB 里没有启用的 chat 模型")
            return

        if len(sys.argv) < 2:
            print("可用 chat 模型（重跑时带序号选择）：")
            for i, m in enumerate(models):
                print(f"  [{i}] {m.provider.name} / {m.model_name}")
            return

        target = models[int(sys.argv[1])]
        print(f"探测目标：{target.provider.name} / {target.model_name}")
        print(f"base_url：{target.base_url or target.provider.base_url}\n")

        model = await build_chat_model(ModelSlot(id=target.id))
        model.stream_usage = True  # 自定义 base_url 时 langchain-openai 默认关，显式开

        print("── 测试 1：流式返不返 usage ──")
        await _stream_once(
            model, [HumanMessage("用一句话回答：1+1=?")], "短请求"
        )

        print("\n── 测试 2：同一长前缀连发两次，看 cache_read ──")
        long_messages = [
            SystemMessage(_LONG_PREFIX),
            HumanMessage("用一句话总结上面背景资料的主题。"),
        ]
        first = await _stream_once(model, long_messages, "第 1 次")
        second = await _stream_once(model, long_messages, "第 2 次")

        print("\n── 结论 ──")
        if second is None:
            print("流式 usage 不可用 → 阈值只能退回字符粗估")
            return
        details = second.get("input_token_details") or {}
        cache_read = details.get("cache_read", 0)
        if cache_read > 0:
            ratio = cache_read / max(second.get("input_tokens", 1), 1)
            print(f"cache 上报 ✅：第 2 次 cache_read={cache_read}（命中率 {ratio:.0%}）")
        else:
            print(
                "usage 有但 cache_read 无/为 0 → 该 provider 不上报（或无）前缀缓存，"
                "cache 命中率指标做不了，input_tokens 阈值仍可用"
            )
        if first is not None:
            f_details = first.get("input_token_details") or {}
            print(f"（对照：第 1 次 input_token_details = {f_details!r}）")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
