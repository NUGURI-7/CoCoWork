from app.core.exceptions.types import ValidationException
from app.services.model.validators.base import BaseModelValidator
from app.services.model.validators.openai_validators import (
    OpenAIChatValidator,
    OpenAIEmbeddingValidator,
)

_defaults: dict[str, BaseModelValidator] = {
    "chat": OpenAIChatValidator(),
    "embedding": OpenAIEmbeddingValidator(),
    "vision": OpenAIChatValidator(),
    "multimodal": OpenAIChatValidator(),
}

_overrides: dict[tuple[str, str], BaseModelValidator] = {
    # ("xunfei", "tts"): XunfeiTTSValidator(),
}


def get_validator(provider_type: str, model_type: str) -> BaseModelValidator:
    """根据 provider_type + model_type 查找对应的 Validator。

    查找顺序：overrides 精确匹配 → defaults 按 model_type 兜底。
    """
    validator = _overrides.get((provider_type, model_type))
    if validator is not None:
        return validator

    validator = _defaults.get(model_type)
    if validator is not None:
        return validator

    raise ValidationException(
        f"不支持的模型类型 '{model_type}'（供应商 '{provider_type}'），暂无对应的验证器",
    )
