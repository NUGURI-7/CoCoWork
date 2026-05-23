from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_admin
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.model import CatalogCreate, CatalogOut
from app.services.model import CatalogService, get_catalog_service

router = APIRouter(prefix="/catalog", tags=["model-catalog"])

AdminDep = Annotated[User, Depends(get_current_admin)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]


@router.post("", summary="添加目录条目")
async def create_catalog_item(
    data: CatalogCreate,
    _admin: AdminDep,
    svc: CatalogServiceDep,
) -> ResponseModel[CatalogOut]:
    item = await svc.create(data)
    return success(data=CatalogOut.model_validate(item), message="创建成功")


@router.delete("/{catalog_id}", summary="删除目录条目")
async def delete_catalog_item(
    catalog_id: UUID,
    _admin: AdminDep,
    svc: CatalogServiceDep,
) -> ResponseModel[None]:
    await svc.delete(catalog_id)
    return success(message="删除成功")


@router.get("", summary="查询目录（按 provider_type 过滤）")
async def list_catalog(
    svc: CatalogServiceDep,
    provider_type: str | None = None,
) -> ResponseModel[list[CatalogOut]]:
    if provider_type:
        items = await svc.list_by_provider_type(provider_type)
    else:
        items = await svc.list_all()
    return success(data=[CatalogOut.model_validate(i) for i in items])
