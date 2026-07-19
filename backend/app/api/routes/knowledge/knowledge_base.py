from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    RetrievalTestOut,
)
from app.services.knowledge import (
    KnowledgeBaseService,
    RetrievalService,
    get_knowledge_base_service,
    get_retrieval_service,
)
from app.services.knowledge.retrieval import RetrievalParams

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

CurrentUserDep = Annotated[User, Depends(get_current_user)]
KnowledgeBaseServiceDep = Annotated[
    KnowledgeBaseService, Depends(get_knowledge_base_service)
]
RetrievalServiceDep = Annotated[
    RetrievalService, Depends(get_retrieval_service)
]


@router.post("", summary="创建知识库")
async def create_knowledge_base(
        data: KnowledgeBaseCreate,
        current_user: CurrentUserDep,
        svc: KnowledgeBaseServiceDep,
) -> ResponseModel[KnowledgeBaseOut]:
    kb = await svc.create(current_user, data)
    return success(data=kb, message="创建成功")


@router.get("", summary="列出自己的知识库")
async def list_knowledge_bases(
        current_user: CurrentUserDep,
        svc: KnowledgeBaseServiceDep,
) -> ResponseModel[list[KnowledgeBaseOut]]:
    kbs = await svc.list_own(current_user)
    return success(data=kbs)


@router.get("/{kb_id}", summary="知识库详情")
async def get_knowledge_base(
        kb_id: UUID,
        current_user: CurrentUserDep,
        svc: KnowledgeBaseServiceDep,
) -> ResponseModel[KnowledgeBaseOut]:
    kb = await svc.get_by_id(current_user, kb_id)
    return success(data=kb)


@router.put("/{kb_id}", summary="更新知识库")
async def update_knowledge_base(
        kb_id: UUID,
        data: KnowledgeBaseUpdate,
        current_user: CurrentUserDep,
        svc: KnowledgeBaseServiceDep,
) -> ResponseModel[KnowledgeBaseOut]:
    kb = await svc.update(current_user, kb_id, data)
    return success(data=kb, message="更新成功")


@router.delete("/{kb_id}", summary="删除知识库")
async def delete_knowledge_base(
        kb_id: UUID,
        current_user: CurrentUserDep,
        svc: KnowledgeBaseServiceDep,
) -> ResponseModel[None]:
    await svc.delete(current_user, kb_id)
    return success(message="删除成功")


@router.post("/{kb_id}/retrieval-test", summary="命中测试（语义检索）")
async def retrieval_test(
    kb_id: UUID,
    params: RetrievalParams,
    current_user: CurrentUserDep,
    svc: RetrievalServiceDep,
) -> ResponseModel[RetrievalTestOut]:
    result = await svc.retrieve(current_user, kb_id, params)
    return success(data=RetrievalTestOut(
        hits=result.hits,
        embed_ms=result.timings.get("embed_ms", 0.0),
        search_ms=result.timings.get("search_ms", 0.0),
        rerank_ms=result.timings.get("rerank_ms", 0.0),
        total_ms=result.timings.get("total_ms", 0.0),
    ))
