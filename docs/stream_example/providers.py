"""
    @project: DaisyWind
    @Author: niu
    @file: providers.py
    @date: 2026/4/10 14:16
    @desc: LLM Provider 工厂：根据 provider 名称构造 PydanticAI Model 实例。
"""
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.google import GoogleProvider

from config import settings


def build_model(provider: str, model_name: str):
    """根据 provider 字符串返回对应的 PydanticAI Model 实例。

    新版 PydanticAI 拆成 Model + Provider 两层：
    - Model 只管模型名
    - Provider 管连接（base_url, api_key）

    Args:
        provider: 厂商标识，如 "deepseek", "gemini"
        model_name: 具体模型名，如 "deepseek-chat", "gemini-3.1-pro-preview"

    Raises:
        ValueError: provider 不在已知列表中
    """
    match provider:
        case "deepseek":
            return OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(
                    base_url="https://api.deepseek.com/v1",
                    api_key=settings.DEEPSEEK_API_KEY,
                ),
            )
        case "gemini":
            return GoogleModel(
                model_name,
                provider=GoogleProvider(
                    api_key=settings.GEMINI_API_KEY,
                ),
            )
        case _:
            raise ValueError(f"Unknown provider: {provider}")