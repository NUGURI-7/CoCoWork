"""AIModel 路由。

URL nested：所有按 provider 的 CRUD 都挂 `/providers/{provider_id}/models` 前缀；
跨 provider 查询和静态元数据另开一个 flat router 挂 `/models`。
两个 router 在本文件 export，由模块 __init__.py 各自 include。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.model import AIModel
from app.models.user import User
from app.schemas.model import (
    PARAM_DEFINITIONS,
    ModelCreate,
    ModelOut,
    ModelTypeParams,
    ModelUpdate,
)
from app.services.model import AIModelService, get_ai_model_service


def _to_model_out(model: AIModel) -> ModelOut:
    """ORM → ModelOut，补充计算字段。"""
    data = ModelOut.model_validate(model)
    data.has_custom_base_url = bool(model.base_url)
    data.has_custom_api_key = bool(model.api_key_encrypted)
    return data


CurrentUserDep = Annotated[User, Depends(get_current_user)]
AIModelServiceDep = Annotated[AIModelService, Depends(get_ai_model_service)]

# ============================================================================
# nested router — /providers/{provider_id}/models
# ============================================================================

nested_router = APIRouter(
    prefix="/providers/{provider_id}/models", tags=["models"],
)


@nested_router.post("", summary="创建模型实例")
async def create_model(
    provider_id: UUID,
    data: ModelCreate,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[ModelOut]:
    model = await svc.create(current_user, provider_id, data)
    return success(data=_to_model_out(model), message="创建成功")


@nested_router.get("", summary="列出某 Provider 下的模型")
async def list_models_by_provider(
    provider_id: UUID,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
    model_type: str | None = Query(default=None, description="按类型过滤"),
    enabled_only: bool = False,
) -> ResponseModel[list[ModelOut]]:
    models = await svc.list_by_provider(
        current_user,
        provider_id,
        model_type=model_type,
        enabled_only=enabled_only,
    )
    return success(data=[_to_model_out(m) for m in models])


@nested_router.get("/{model_id}", summary="模型详情")
async def get_model(
    provider_id: UUID,
    model_id: UUID,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[ModelOut]:
    model = await svc.get_by_id(current_user, provider_id, model_id)
    return success(data=_to_model_out(model))


@nested_router.put("/{model_id}", summary="更新模型实例")
async def update_model(
    provider_id: UUID,
    model_id: UUID,
    data: ModelUpdate,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[ModelOut]:
    model = await svc.update(current_user, provider_id, model_id, data)
    return success(data=_to_model_out(model), message="更新成功")


@nested_router.delete("/{model_id}", summary="删除模型实例")
async def delete_model(
    provider_id: UUID,
    model_id: UUID,
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, provider_id, model_id)
    return success(message="删除成功")


# ============================================================================
# flat router — /models（跨 provider 查询 + 静态元数据）
# ============================================================================

flat_router = APIRouter(prefix="/models", tags=["models"])


@flat_router.get("/param-definitions", summary="参数定义（动态表单元数据）")
async def get_param_definitions(
    _current_user: CurrentUserDep,
) -> ResponseModel[dict[str, ModelTypeParams]]:
    return success(data=PARAM_DEFINITIONS)


@flat_router.get("", summary="跨 Provider 列出自己的所有模型")
async def list_all_models(
    current_user: CurrentUserDep,
    svc: AIModelServiceDep,
    model_type: str | None = Query(default=None, description="按类型过滤"),
    enabled_only: bool = False,
) -> ResponseModel[list[ModelOut]]:
    models = await svc.list_own(
        current_user,
        model_type=model_type,
        enabled_only=enabled_only,
    )
    return success(data=[_to_model_out(m) for m in models])
