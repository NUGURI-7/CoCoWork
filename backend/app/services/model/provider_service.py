import logging
from uuid import UUID

from app.core.exceptions.types import NotFound404, ValidationException
from app.services.model.credentials import dump_credentials
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
            credentials_encrypted=dump_credentials(data.provider_type, data.credentials),
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
        # 凭证形状跟着 provider_type 走：本次改了就按新类型打包，没改按原类型
        provider_type = data.provider_type or provider.provider_type
        if data.credentials is not None:
            update_fields["credentials_encrypted"] = dump_credentials(
                provider_type, data.credentials,
            )
        elif provider_type != provider.provider_type:
            raise ValidationException(
                "改供应商类型时必须同时重填凭证——不同供应商的凭证字段不同",
            )
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



async def get_provider_service() -> ProviderService:
    return ProviderService()
