from uuid import UUID

from tortoise.exceptions import IntegrityError

from app.core.exceptions.types import NotFound404, ValidationException
from app.models.model import ProviderModelCatalog
from app.schemas.model import CatalogCreate


class CatalogService:
    """供应商模型目录 CRUD，仅管理员操作。"""

    async def create(self, data: CatalogCreate) -> ProviderModelCatalog:
        try:
            return await ProviderModelCatalog.create(
                provider_type=data.provider_type,
                model_id=data.model_id,
                model_type=data.model_type,
            )
        except IntegrityError as e:
            raise ValidationException(
                f"模型 '{data.model_id}' 在 '{data.provider_type}' 下已存在",
            ) from e

    async def delete(self, catalog_id: UUID) -> None:
        item = await ProviderModelCatalog.filter(id=catalog_id).first()
        if item is None:
            raise NotFound404("目录条目不存在")
        await item.delete()

    async def list_by_provider_type(self, provider_type: str) -> list[ProviderModelCatalog]:
        return await ProviderModelCatalog.filter(
            provider_type=provider_type,
        ).order_by("model_type", "model_id")

    async def list_all(self) -> list[ProviderModelCatalog]:
        return await ProviderModelCatalog.all().order_by(
            "provider_type", "model_type", "model_id",
        )


async def get_catalog_service() -> CatalogService:
    return CatalogService()
