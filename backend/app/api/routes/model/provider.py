from typing import Annotated, get_args
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.model import ProviderCreate, ProviderOut, ProviderType, ProviderUpdate
from app.services.model import ProviderService, get_provider_service
from app.services.model.credentials import CredentialField, credential_fields

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


# 必须注册在 /{provider_id} 之前：FastAPI 按顺序匹配，放到后面会先撞上路径参数，
# 拿 "credential-definitions" 去解析 UUID 直接 422
@router.get("/credential-definitions", summary="凭证字段定义（动态表单元数据）")
async def get_credential_definitions(
    _current_user: CurrentUserDep,
) -> ResponseModel[dict[str, list[CredentialField]]]:
    """按 provider_type 返回各家要填哪些凭证字段，前端据此渲染表单。"""
    return success(
        data={pt: credential_fields(pt) for pt in get_args(ProviderType)},
    )


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


