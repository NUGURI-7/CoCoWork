"""Provider 参数适配器 —— 规范化 ModelParams → init_chat_model 入参。

为什么要这层：
- 我们用 langchain 的 OpenAI 适配器（init_chat_model(model_provider="openai")）统一对接
  所有 OpenAI 兼容端点（DeepSeek / 通义 / SiliconFlow / custom...）。
- 但 langchain-openai 会把顶层 max_tokens 无条件改名成 max_completion_tokens（OpenAI
  2024-09 起的新字段）；多数兼容端点只认老字段 max_tokens、不认新字段，上限被静默丢弃。
- 故把「规范参数 → 各 provider 家族实际入参」收成一层适配器：基类全透传，各家族子类只覆盖
  自己的方言，按 LC provider 家族注册。新增方言改一个类、新增家族加一行，build_chat_model
  不再做 if/dict 手术。

key 用 LC provider 家族（init_chat_model 的 model_provider），不是业务 provider_type：
quirk 属于 langchain 集成本身，deepseek / dashscope 都映射到 openai 家族、共享同套方言。
"""

from typing import Any


class ProviderParamAdapter:
    """基类：规范化 ModelParams → init_chat_model 入参。

    默认 = 全透传顶层（temperature / top_p / ... 各 provider 同名同义）。
    子类仅在有方言差异时覆盖 to_init_kwargs。
    """

    def to_init_kwargs(self, params: dict[str, Any]) -> dict[str, Any]:
        return dict(params)


class OpenAIParamAdapter(ProviderParamAdapter):
    """OpenAI 兼容家族（含 DeepSeek / 通义 / SiliconFlow / custom 兼容端点）。

    langchain-openai 把顶层 max_tokens 改名成 max_completion_tokens，兼容端点多不认 →
    走 OpenAI SDK 公开的 extra_body 通道原样发 max_tokens，符合这些端点的 API 契约。
    setdefault 合并：不覆盖用户经 extra="allow" 自带的 extra_body。
    """

    def to_init_kwargs(self, params: dict[str, Any]) -> dict[str, Any]:
        kwargs = dict(params)
        max_tokens = kwargs.pop("max_tokens", None)
        if max_tokens is not None:
            kwargs.setdefault("extra_body", {})["max_tokens"] = max_tokens
        return kwargs


# LC provider 家族 → 参数适配器实例（缺省回落基类透传）
_PARAM_ADAPTERS: dict[str, ProviderParamAdapter] = {
    "openai": OpenAIParamAdapter(),
    "anthropic": ProviderParamAdapter(),  # 原生 max_tokens，透传即可
}

_DEFAULT_PARAM_ADAPTER = ProviderParamAdapter()


def get_param_adapter(lc_provider: str) -> ProviderParamAdapter:
    """按 LC provider 家族取参数适配器；未注册的回落透传基类。"""
    return _PARAM_ADAPTERS.get(lc_provider, _DEFAULT_PARAM_ADAPTER)