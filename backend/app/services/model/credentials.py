"""供应商凭证：形状按 provider_type 声明，整包 JSON 加密后存一列。

存在的理由是**不同供应商的凭证形状根本不同**——OpenAI 兼容那派一个 api_key 就够，
百度要 API Key + Secret Key 换 access_token。一列裸字符串装不下，故统一成「加密的
凭证包」：列里恒为 Fernet 加密的 JSON，形状由本模块声明。

不是新发明：MCP server 的 headers_encrypted 就是整包 JSON 后加密；MaxKB 的
Model.credential 同样是一列存加密后的凭证 JSON。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.fields import FieldInfo

from app.core.encryption import decrypt, encrypt
from app.core.exceptions.types import ValidationException


class BaseCredentials(BaseModel):
    """凭证包基类。

    `extra="ignore"`：读库方向要宽松——某天凭证模型删掉一个字段，存量行不该因此
    整个读不出来。写入方向的严格由 dump 那侧单独把关（下一步写）。

    `api_key` 定在基类而非各子类：它是唯一一个所有供应商都有的字段，定在这里，
    下游通用路径（如 `ModelClient`）拿到 `BaseCredentials` 就能直接 `.api_key`。
    """

    model_config = ConfigDict(extra="ignore")

    api_key: str = Field(
        default="",
        json_schema_extra={"label": "API Key", "secret": True},
    )


class ApiKeyCredentials(BaseCredentials):
    """OpenAI 兼容那派：一个 api_key 走天下。

    `default=""` 是照顾现状——现有 Provider 允许空 Key（`ModelClient.build_client`
    专门处理过「不带鉴权请求上游」那种自托管场景），改成必填会把那条路堵死。
    """


class BaiduCredentials(BaseCredentials):
    """百度智能云：API Key + Secret Key 换 access_token（30 天有效）。"""

    api_key: str = Field(
        min_length=1,
        json_schema_extra={"label": "API Key", "secret": True},
    )
    secret_key: str = Field(
        min_length=1,
        json_schema_extra={"label": "Secret Key", "secret": True},
    )


# 装配硬编码：凭证形状是代码事实、不是部署变量，同 validators 的注册表。
# 未登记的 provider_type 一律按单 key 兜底——OpenAI 兼容是这行当的默认形状，
# `custom` 那类自定义端点也归这里。
_CREDENTIAL_MODELS: dict[str, type[BaseCredentials]] = {
    "baidu": BaiduCredentials,
}


def credential_model(provider_type: str) -> type[BaseCredentials]:
    """取某供应商的凭证模型。未登记则按单 key 兜底。"""
    return _CREDENTIAL_MODELS.get(provider_type, ApiKeyCredentials)


def dump_credentials(provider_type: str, raw: dict[str, Any]) -> str:
    """明文凭证 dict → 加密串。字段缺失 / 拼错在此拦下。

    多余字段**主动报错而不是静默丢弃**——与读库方向的 `extra="ignore"` 刻意相反。
    用户把 `secret_key` 拼成 `secretKey` 时，静默丢弃的表现是「保存成功了、一调用
    就 401」，排查成本远高于当场拒绝。
    """
    model = credential_model(provider_type)

    unknown = set(raw) - set(model.model_fields)

    if unknown:
        raise ValidationException(
            f"供应商 '{provider_type}' 不认识这些凭证字段：{sorted(unknown)}",
        )

    try:
        creds = model(**raw)
    except ValidationError as e:
        raise ValidationException(f"凭证字段不合法：{e}") from e

    return encrypt(creds.model_dump_json())


def load_credentials(provider_type: str, ciphertext: str) -> BaseCredentials:
    """加密串 → 类型化凭证对象。

    抛 `ValueError` 而非 `ValidationException`：走到这里出错说明加密密钥换了、
    或迁移漏了行，属运维 / 编程错误，不是用户填错，不该包装成面向用户的文案。
    """
    if not ciphertext:
        raise ValueError("凭证为空：调用方应先做 Model 级 → Provider 级的回退")

    model = credential_model(provider_type)
    try:
        return model.model_validate_json(decrypt(ciphertext))
    except ValidationError as e:
        raise ValueError(f"凭证包格式不对（provider_type={provider_type}）：{e}") from e


class CredentialField(BaseModel):
    """一个凭证字段的表单定义，前端据此渲染控件。

    形状刻意对齐 `ParamField`（模型参数那套动态表单）——前端渲染凭证和渲染
    参数走同一个路子，不必为凭证另学一套。
    """

    key: str
    label: str
    secret: bool = True
    required: bool = True


def _ui(field: FieldInfo) -> dict[str, Any]:
    """取字段上挂的 UI 元信息。

    `json_schema_extra` 在 Pydantic 里也允许是个回调函数（用来动态改 schema），
    本模块只用 dict 形式，非 dict 一律当没挂。
    """
    extra = field.json_schema_extra
    return extra if isinstance(extra, dict) else {}


def credential_fields(provider_type: str) -> list[CredentialField]:
    """导出某供应商的凭证表单定义，顺序即图纸上的字段顺序。"""
    return [
        CredentialField(
            key=name,
            label=_ui(field).get("label", name),
            secret=_ui(field).get("secret", True),
            required=field.is_required(),
        )
        for name, field in credential_model(provider_type).model_fields.items()
    ]
