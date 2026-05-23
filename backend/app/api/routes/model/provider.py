from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.model import ProviderCreate, ProviderOut, ProviderUpdate
from app.services.model import ProviderService, get_provider_service

router = APIRouter(prefix="/providers", tags=["providers"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]
ProviderServiceDep = Annotated[ProviderService, Depends(get_provider_service)]


@router.post("", summary="创建 Provider")
async def create_provider(
    data: ProviderCreate,
    current_user: CurrentUserDep,
    svc: ProviderServiceDep,
) -> ResponseModel[ProviderOut]:
    provider = await svc.create(current_user, data)
    return success(data=ProviderOut.model_validate(provider), message="创建成功")


@router.get("", summary="列出自己的 Provider")
async def list_providers(
    current_user: CurrentUserDep,
    svc: ProviderServiceDep,
) -> ResponseModel[list[ProviderOut]]:
    providers = await svc.list_own(current_user)
    return success(data=[ProviderOut.model_validate(p) for p in providers])


@router.get("/{provider_id}", summary="Provider 详情")
async def get_provider(
    provider_id: UUID,
    current_user: CurrentUserDep,
    svc: ProviderServiceDep,
) -> ResponseModel[ProviderOut]:
    provider = await svc.get_by_id(current_user, provider_id)
    return success(data=ProviderOut.model_validate(provider))


@router.put("/{provider_id}", summary="更新 Provider")
async def update_provider(
    provider_id: UUID,
    data: ProviderUpdate,
    current_user: CurrentUserDep,
    svc: ProviderServiceDep,
) -> ResponseModel[ProviderOut]:
    provider = await svc.update(current_user, provider_id, data)
    return success(data=ProviderOut.model_validate(provider), message="更新成功")


@router.delete("/{provider_id}", summary="删除 Provider")
async def delete_provider(
    provider_id: UUID,
    current_user: CurrentUserDep,
    svc: ProviderServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, provider_id)
    return success(message="删除成功")


