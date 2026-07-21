import logging
from uuid import UUID

from tortoise.functions import Count, Sum
from tortoise.queryset import QuerySet

from app.core.exceptions.types import NotFound404, ValidationException
from app.models.knowledge import KnowledgeBase, KBStatus
from app.models.model import AIModel
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from app.services.model.model_client import ModelClient

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """知识库 CRUD。可见性：用户只能看到自己创建的库。

    读取方法直接返回组装好的 KnowledgeBaseOut（含 embedding 模型名 + 文档/子块计数）：
    计数走 annotate（注意不能与 select_related 同用，否则被 join 的列不在 GROUP BY），
    模型名用一次批量查询补，避免 N+1。
    """

    def _annotated_query(self, user: User) -> QuerySet[KnowledgeBase]:
        """带文档/子块计数的查询（不 select_related，规避 GROUP BY 冲突）。"""
        return KnowledgeBase.filter(created_by=user).annotate(
            doc_count=Count("documents", distinct=True),
            chunk_count=Sum("documents__chunk_count"),
        )

    async def _assemble(self, kbs: list[KnowledgeBase]) -> list[KnowledgeBaseOut]:
        """ORM（带 annotate 计数）→ KnowledgeBaseOut，批量补 embedding 模型名。"""
        if not kbs:
            return []
        model_ids = {kb.embedding_model_id for kb in kbs}
        rerank_ids = {kb.rerank_model_id for kb in kbs if kb.rerank_model_id}
        all_ids = model_ids | rerank_ids
        name_map = dict(
            await AIModel.filter(id__in=all_ids).values_list("id", "display_name")
        )
        return [
            KnowledgeBaseOut(
                id=kb.id,
                name=kb.name,
                description=kb.description,
                embedding_model_id=kb.embedding_model_id,
                embedding_model_name=name_map.get(kb.embedding_model_id, ""),
                embedding_dim=kb.embedding_dim,
                chunk_config=kb.chunk_config,
                status=kb.status,
                doc_count=getattr(kb, "doc_count", 0) or 0,
                chunk_count=getattr(kb, "chunk_count", 0) or 0,
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                retrieval_mode=kb.retrieval_mode,
                rerank_model_id=kb.rerank_model_id,
                rerank_model_name=name_map.get(kb.rerank_model_id) if kb.rerank_model_id else None,
            )
            for kb in kbs
        ]

    async def get_by_id(self, user: User, kb_id: UUID) -> KnowledgeBaseOut:
        """获取用户自己的知识库，不存在或非本人则 404。"""
        kbs = await self._annotated_query(user).filter(id=kb_id)
        if not kbs:
            raise NotFound404("知识库不存在")
        return (await self._assemble(kbs))[0]

    async def list_own(self, user: User) -> list[KnowledgeBaseOut]:
        """返回用户自己创建的知识库。"""
        kbs = await self._annotated_query(user).order_by("-created_at")
        return await self._assemble(kbs)

    async def create(self, user: User, data: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        # 1. 校验 embedding 模型归属 + 类型
        model = (
            await AIModel.filter(id=data.embedding_model_id, provider__created_by=user)
            .select_related("provider")
            .first()
        )
        if model is None:
            raise NotFound404("Embedding 模型不存在")
        if model.model_type != "embedding":
            raise ValidationException("知识库必须绑定 embedding 类型的模型")

        # 2. 解析向量维度：优先读 meta 缓存，缺失则探测一次并回写
        dim = (model.meta or {}).get("embedding_dim")
        if not dim:
            dim = await self._probe_embedding_dim(model)

        # 3. 入库
        kb = await KnowledgeBase.create(
            created_by=user,
            name=data.name,
            description=data.description,
            embedding_model=model,
            embedding_dim=dim,
            chunk_config=data.chunk_config.model_dump(),
            status=KBStatus.READY,
        )

        return await self.get_by_id(user, kb.id)

    async def _probe_embedding_dim(self, model: AIModel) -> int:
        """实测 embedding 维度并回写 AIModel.meta（仅旧模型/缺失时兜底）。"""
        try:
            vectors = await ModelClient.create_embedding(model, ["dimension probe"])
            dim = len(vectors[0])
        except Exception as e:
            logger.warning("探测 embedding 维度失败: %s %s", model.model_name, e)
            raise ValidationException(f"无法确定向量维度: {e}") from e

        model.meta = {**(model.meta or {}), "embedding_dim": dim}
        await model.save(update_fields=["meta"])
        return dim

    async def update(
        self, user: User, kb_id: UUID, data: KnowledgeBaseUpdate,
    ) -> KnowledgeBaseOut:
        if not await KnowledgeBase.filter(created_by=user, id=kb_id).exists():
            raise NotFound404("知识库不存在")

        update_fields: dict = {}
        if data.name is not None:
            update_fields["name"] = data.name
        if data.description is not None:
            update_fields["description"] = data.description
        if data.chunk_config is not None:
            update_fields["chunk_config"] = data.chunk_config.model_dump()
        if data.retrieval_mode is not None:
            update_fields["retrieval_mode"] = data.retrieval_mode.value

        if "rerank_model_id" in data.model_fields_set:
            if data.rerank_model_id is None:
                update_fields["rerank_model_id"] = None
            else:
                rerank_model = await AIModel.filter(
                    id=data.rerank_model_id, provider__created_by=user,
                ).first()
                if rerank_model is None:
                    raise NotFound404("精排模型不存在")
                if rerank_model.model_type != "rerank":
                    raise ValidationException("精排模型必须为 rerank 类型")
                update_fields["rerank_model_id"] = data.rerank_model_id

        if update_fields:
            await KnowledgeBase.filter(id=kb_id).update(**update_fields)

        return await self.get_by_id(user, kb_id)

    async def delete(self, user: User, kb_id: UUID) -> None:
        kb = await KnowledgeBase.filter(created_by=user, id=kb_id).first()
        if kb is None:
            raise NotFound404("知识库不存在")
        await kb.delete()


async def get_knowledge_base_service() -> KnowledgeBaseService:
    return KnowledgeBaseService()
