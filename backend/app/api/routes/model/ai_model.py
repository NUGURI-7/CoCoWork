from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.model import (
    PARAM_DEFINITIONS,
    ModelCreate,
    ModelOut,
    ModelTypeParams,
    ModelUpdate,
)
from app.models.model import AIModel
from app.services.model import AIModelService, get_ai_model_service

router = APIRouter(prefix="/models", tags=["models"])


def _to_model_out(model: AIModel) -> ModelOut:
    """ORM → ModelOut，补充计算字段。"""
    data = ModelOut.model_validate(model)
    data.has_custom_base_url = bool(model.base_url)
    data.has_custom_api_key = bool(model.api_key_encrypted)
    return data

CurrentUserDep = Annotated[User, Depends(get_current_user)]
AIModelServiceDep = Annotated[AIModelService, Depends(get_ai_model_service)]


@router.get("/param-definitions", summary="参数定义（动态表单元数据）")
async def get_param_definitions(
    _current_user: CurrentUserDep,
) -> ResponseModel[dict[str, ModelTypeParams]]:
    return success(data=PARAM_DEFINITIONS)


@router.post("", summary="创建模型实例")
async def create_model(
    data: ModelCreate,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[ModelOut]:
    model = await svc.create(current_user, data)
    return success(data=_to_model_out(model), message="创建成功")


@router.get("", summary="列出自己的模型")
async def list_models(
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
    provider_id: UUID | None = Query(default=None, description="按 Provider 过滤"),
    model_type: str | None = Query(default=None, description="按类型过滤"),
    enabled_only: bool = False,
) -> ResponseModel[list[ModelOut]]:
    models = await svc.list_own(
        current_user,
        provider_id=provider_id,
        model_type=model_type,
        enabled_only=enabled_only,
    )
    return success(data=[_to_model_out(m) for m in models])


@router.get("/{model_id}", summary="模型详情")
async def get_model(
    model_id: UUID,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[ModelOut]:
    model = await svc.get_by_id(current_user, model_id)
    return success(data=_to_model_out(model))


@router.put("/{model_id}", summary="更新模型实例")
async def update_model(
    model_id: UUID,
    data: ModelUpdate,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[ModelOut]:
    model = await svc.update(current_user, model_id, data)
    return success(data=_to_model_out(model), message="更新成功")


@router.delete("/{model_id}", summary="删除模型实例")
async def delete_model(
    model_id: UUID,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, model_id)
    return success(message="删除成功")
