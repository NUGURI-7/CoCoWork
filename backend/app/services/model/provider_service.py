import logging
from uuid import UUID

from app.core.encryption import decrypt, encrypt
from app.core.exceptions.types import NotFound404
from app.models.model import Provider
from app.models.user import User
from app.schemas.model import ProviderCreate, ProviderUpdate

logger = logging.getLogger(__name__)


class ProviderService:
    """Provider CRUD。

    可见性：用户只能看到自己创建的 Provider。
    管理员授权共享的能力后续再加。
    """

    async def get_by_id(self, user: User, provider_id: UUID) -> Provider:
        """获取用户自己的 Provider，不存在或非本人则 404。"""
        provider = await Provider.filter(id=provider_id, created_by=user).first()
        if provider is None:
            raise NotFound404("Provider 不存在")
        return provider

    async def create(self, user: User, data: ProviderCreate) -> Provider:
        return await Provider.create(
            created_by=user,
            name=data.name,
            provider_type=data.provider_type,
            base_url=data.base_url,
            api_key_encrypted=encrypt(data.api_key),
            description=data.description,
        )

    async def update(self, user: User, provider_id: UUID, data: ProviderUpdate) -> Provider:
        provider = await self.get_by_id(user, provider_id)

        update_fields: dict = {}
        if data.name is not None:
            update_fields["name"] = data.name
        if data.provider_type is not None:
            update_fields["provider_type"] = data.provider_type
        if data.base_url is not None:
            update_fields["base_url"] = data.base_url
        if data.api_key is not None:
            update_fields["api_key_encrypted"] = encrypt(data.api_key)
        if data.description is not None:
            update_fields["description"] = data.description

        if not update_fields:
            return provider

        await Provider.filter(id=provider_id).update(**update_fields)

        return await Provider.get(id=provider_id)

    async def list_own(self, user: User) -> list[Provider]:
        """返回用户自己创建的 Provider。"""
        return await Provider.filter(created_by=user).order_by("-created_at")

    async def delete(self, user: User, provider_id: UUID) -> None:
        provider = await self.get_by_id(user, provider_id)
        await provider.delete()

    async def get_decrypted_key(self, provider: Provider) -> str:
        """解密 API Key（仅内部调用，不暴露给路由层）。"""
        return decrypt(provider.api_key_encrypted)


async def get_provider_service() -> ProviderService:
    return ProviderService()
