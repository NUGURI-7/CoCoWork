import logging
from uuid import UUID

from app.core.encryption import decrypt, encrypt
from app.core.exceptions.types import NotFound404
from app.models.model import AIModel, Provider
from app.models.user import User
from app.schemas.model import ModelCreate, ModelUpdate
from app.services.model.model_client import ModelClient
from app.services.model.validators import get_validator

logger = logging.getLogger(__name__)


class AIModelService:
    """AIModel CRUD，归属通过 Provider 链路校验。"""

    async def get_by_id(self, user: User, model_id: UUID) -> AIModel:
        """获取用户自己的 AIModel（通过 provider.created_by 校验归属）。"""
        model = await AIModel.filter(
            id=model_id, provider__created_by=user,
        ).first()
        if model is None:
            raise NotFound404("模型不存在")
        return model

    async def create(self, user: User, data: ModelCreate) -> AIModel:
        # 1. 校验 Provider 归属
        provider = await Provider.filter(
            id=data.provider_id, created_by=user,
        ).first()
        if provider is None:
            raise NotFound404("Provider 不存在")

        # 2. 解析凭证：Model 级覆盖 > Provider 级
        base_url = data.base_url or provider.base_url
        api_key = data.api_key or decrypt(provider.api_key_encrypted)

        # 3. 连通性验证
        client = ModelClient.build_client(base_url, api_key)
        validator = get_validator(provider.provider_type, data.model_type)
        await validator.validate(client, data.model_name)

        # 4. 验证通过，入库
        model = await AIModel.create(
            provider_id=data.provider_id,
            model_name=data.model_name,
            display_name=data.display_name,
            model_type=data.model_type,
            config=data.config,
            base_url=data.base_url or "",
            api_key_encrypted=encrypt(data.api_key) if data.api_key else "",
            is_enabled=data.is_enabled,
        )
        return await AIModel.filter(id=model.id).first()

    async def update(self, user: User, model_id: UUID, data: ModelUpdate) -> AIModel:
        model = await self.get_by_id(user, model_id)

        update_fields: dict = {}
        if data.model_name is not None:
            update_fields["model_name"] = data.model_name
        if data.display_name is not None:
            update_fields["display_name"] = data.display_name
        if data.model_type is not None:
            update_fields["model_type"] = data.model_type
        if data.config is not None:
            update_fields["config"] = data.config
        if data.base_url is not None:
            update_fields["base_url"] = data.base_url
        if data.api_key is not None:
            update_fields["api_key_encrypted"] = encrypt(data.api_key) if data.api_key else ""
        if data.is_enabled is not None:
            update_fields["is_enabled"] = data.is_enabled

        if not update_fields:
            return model

        # 凭证或模型名变了，需要重新验证连通性
        need_validate = any(k in update_fields for k in ("base_url", "api_key_encrypted", "model_name"))
        if need_validate:
            provider = await Provider.filter(id=model.provider_id).first()

            base_url = update_fields.get("base_url", model.base_url) or provider.base_url
            if "api_key_encrypted" in update_fields:
                api_key = data.api_key
            else:
                api_key = decrypt(model.api_key_encrypted) if model.api_key_encrypted else decrypt(provider.api_key_encrypted)
            model_name = update_fields.get("model_name", model.model_name)
            model_type = update_fields.get("model_type", model.model_type)

            client = ModelClient.build_client(base_url, api_key)
            validator = get_validator(provider.provider_type, model_type)
            await validator.validate(client, model_name)

        await AIModel.filter(id=model_id).update(**update_fields)
        return await AIModel.filter(id=model_id).first()

    async def list_own(
        self,
        user: User,
        provider_id: UUID | None = None,
        model_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[AIModel]:
        """返回用户自己的 AIModel（通过 Provider 链路）。"""
        qs = AIModel.filter(provider__created_by=user)

        if provider_id:
            qs = qs.filter(provider_id=provider_id)
        if model_type:
            qs = qs.filter(model_type=model_type)
        if enabled_only:
            qs = qs.filter(is_enabled=True)

        return await qs.order_by("-created_at")

    async def delete(self, user: User, model_id: UUID) -> None:
        model = await self.get_by_id(user, model_id)
        await model.delete()


async def get_ai_model_service() -> AIModelService:
    return AIModelService()
