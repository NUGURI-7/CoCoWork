"""Document（知识库文档）CRUD service。

只管「元数据 + storage 对象生命周期」，不含文件字节流上传（路由层的事）。
URL nested → 所有方法第一参数固定 (user, kb_id, ...)，doc_id 永远在 kb_id 之后。
可见性：用户只能操作自己创建的 KB 下的文档。
"""

import logging
from pathlib import PurePosixPath
from uuid import UUID

from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from app.core.config import settings
from app.core.exceptions.types import AppApiException, NotFound404, ValidationException
from app.core.storage import storage
from app.models.knowledge import Document, KnowledgeBase, DocStatus, DocStage
from app.models.user import User
from app.schemas.knowledge import ALLOWED_FILE_TYPES
from app.tasks.registry import INDEX_DOCUMENT, PARSE_DOCUMENT, TaskSpec

logger = logging.getLogger(__name__)


def _parse_file_type(name: str) -> str:
    """从文件名取小写扩展名（不带点）；无扩展名 → 空串（落白名单校验）。"""
    return PurePosixPath(name).suffix.lstrip(".").lower()


def _build_storage_key(kb_id: UUID, doc_id: UUID, file_type: str) -> str:
    """约定 `kb/{kb_id}/doc/{doc_id}.{ext}`。两后端通用（R2=对象 key，Local=相对路径）。"""
    return f"kb/{kb_id}/doc/{doc_id}.{file_type}"


def build_doc_prefix(kb_id: UUID, doc_id: UUID) -> str:
    """文档派生对象（解析出的图等）的目录前缀 `kb/{kb_id}/doc/{doc_id}/`。

    与原件 `kb/{kb_id}/doc/{doc_id}.{ext}` 同级不同名：原件不在这个目录里，删文档两样都要删。
    """
    return f"kb/{kb_id}/doc/{doc_id}/"


# 可触发解析：已上传待处理 / 已解析、已完成（重新解析）/ 任意一步失败
_PARSABLE = (
    Q(status=DocStatus.PENDING, stage=DocStage.UPLOADED)
    | Q(status__in=[DocStatus.PARSED, DocStatus.COMPLETED, DocStatus.FAILED])
)

# 可触发建索引：已解析 / 已完成（重建）/ 建索引那步失败。
# 解析那步失败时没有可用的新段落，须先重新解析
_INDEXABLE = (
    Q(status__in=[DocStatus.PARSED, DocStatus.COMPLETED])
    | Q(status=DocStatus.FAILED, stage=DocStage.EMBEDDING)
)


def _reject_reason(doc: Document) -> str:
    """触发被拒时，按文档当前状态说明原因。"""
    if doc.status == DocStatus.PROCESSING:
        return "文档处理中，请稍候"
    if doc.status == DocStatus.PENDING:
        return "文档尚未解析" if doc.stage == DocStage.UPLOADED else "文档尚未上传完成"
    # 走到这里只剩一种：解析那步失败的文档点了建索引
    return "解析失败，请先重新解析"


class DocumentService:
    """文档 CRUD（元数据 + storage 对象生命周期）。"""

    async def _ensure_user_kb(self, user: User, kb_id: UUID) -> KnowledgeBase:
        """校验 kb 归属当前用户，返回 kb 实例（用于 create 时挂 FK）。"""
        kb = await KnowledgeBase.filter(created_by=user, id=kb_id).first()
        if kb is None:
            raise NotFound404("知识库不存在")
        return kb

    async def _get_user_doc(
            self, user: User, kb_id: UUID, doc_id: UUID,
    ) -> Document:
        """取 doc，同时校验 doc 在 kb 下 + kb 归属当前用户。一次 SQL JOIN。"""
        doc = await Document.filter(
            id=doc_id,
            knowledge_base_id=kb_id,
            knowledge_base__created_by=user,
        ).first()
        if doc is None:
            raise NotFound404("文档不存在")
        return doc

    async def create_pending(
            self, user: User, kb_id: UUID, name: str, size: int,
    ) -> Document:
        """建一条 pending 文档记录（占位，尚未真传字节）。

        校验：扩展名白名单 + 大小上限。storage_key 含 doc_id，故 create
        占位 → 拿到 id → update 回填。
        """
        kb = await self._ensure_user_kb(user, kb_id)

        file_type = _parse_file_type(name)
        if file_type not in ALLOWED_FILE_TYPES:
            allowed = ", ".join(sorted(ALLOWED_FILE_TYPES))
            raise ValidationException(
                f"不支持的文件类型 .{file_type}（允许：{allowed}）"
            )

        if size > settings.STORAGE_MAX_UPLOAD_SIZE:
            mb = settings.STORAGE_MAX_UPLOAD_SIZE // (1024 * 1024)
            raise ValidationException(f"文件超出大小上限 {mb}MB")

        doc = await Document.create(
            knowledge_base=kb,
            name=name,
            file_type=file_type,
            size=size,
            storage_key="",  # 占位，拿到 id 后回填
            status=DocStatus.PENDING,
        )
        doc.storage_key = _build_storage_key(kb.id, doc.id, file_type)
        await doc.save(update_fields=["storage_key"])
        return doc

    async def list_by_kb(self, user: User, kb_id: UUID) -> list[Document]:
        """列出库下所有文档（按创建时间倒序）。"""
        await self._ensure_user_kb(user, kb_id)
        return await Document.filter(knowledge_base_id=kb_id).order_by("-created_at")

    def query_by_kb(self, user: User, kb_id: UUID) -> QuerySet[Document]:
        """构造列出库下文档的 QuerySet（按创建时间倒序，未执行）。

        归属直接压进 JOIN 过滤：非本人库 → 空结果（不泄漏库是否存在）。
        """
        return Document.filter(
            knowledge_base_id=kb_id,
            knowledge_base__created_by=user,
        ).order_by("-created_at")

    async def get_by_id(
            self, user: User, kb_id: UUID, doc_id: UUID,
    ) -> Document:
        return await self._get_user_doc(user, kb_id, doc_id)

    async def mark_uploaded(self, user: User, kb_id: UUID, doc_id: UUID, ) -> Document:
        """文件传完后调：跟 storage 复校真实大小、超限就清理、否则置 stage=uploaded。"""
        doc = await self._get_user_doc(user, kb_id, doc_id)

        try:
            actual_size = await storage.stat_size(doc.storage_key)
        except FileNotFoundError as e:
            raise ValidationException("文件未在存储中找到，上传可能未完成") from e

        if actual_size > settings.STORAGE_MAX_UPLOAD_SIZE:
            mb = settings.STORAGE_MAX_UPLOAD_SIZE // (1024 * 1024)
            # 超限：清干净（storage 对象 + ORM 记录）+ 抛错
            try:
                await storage.delete(doc.storage_key)
            except Exception as e:
                logger.warning(
                    "超限清理 storage 失败 doc_id=%s key=%s: %s",
                    doc.id, doc.storage_key, e,
                )
            await doc.delete()
            raise ValidationException(f"文件超出大小上限 {mb}MB")

        doc.size = actual_size
        doc.stage = DocStage.UPLOADED
        await doc.save(update_fields=["size", "stage"])
        return doc

    async def trigger_parse(self, user: User, kb_id: UUID, doc_id: UUID) -> Document:
        """触发解析：首次解析、重新解析、失败重试都走这里。"""
        return await self._trigger(user, kb_id, doc_id, _PARSABLE, PARSE_DOCUMENT)

    async def trigger_index(self, user: User, kb_id: UUID, doc_id: UUID) -> Document:
        """触发建索引：首次建、重建、建索引失败重试都走这里。"""
        return await self._trigger(user, kb_id, doc_id, _INDEXABLE, INDEX_DOCUMENT)

    async def _trigger(
            self, user: User, kb_id: UUID, doc_id: UUID, allowed: Q, task: TaskSpec,
    ) -> Document:
        """检查状态并改成处理中，再入队。"""
        doc = await self._get_user_doc(user, kb_id, doc_id)
        if not await self._claim(doc, allowed):
            # 按当前状态说原因：被另一个请求抢先时，当前状态已是处理中
            await doc.refresh_from_db(fields=["status", "stage"])
            raise ValidationException(_reject_reason(doc))
        if not await self._enqueue(doc, task):
            raise AppApiException(code=503, message="任务队列不可用，请稍后重试")

        doc.status = DocStatus.PROCESSING
        doc.stage = DocStage.QUEUED
        doc.error_message = ""
        return doc

    @staticmethod
    async def _claim(doc: Document, allowed: Q) -> bool:
        """带条件的 UPDATE：状态符合规则才改成处理中 / 排队中，返回是否改成功。

        检查和改状态是同一条语句：连点两下时只有一个请求改得动，不会入队两个任务。
        同步置 queued：DB 立即反映「已入队待处理」，刷新页面也能正确续轮询。
        """
        updated = await Document.filter(allowed, id=doc.id).update(
            status=DocStatus.PROCESSING, stage=DocStage.QUEUED, error_message="",
        )
        return updated > 0

    @staticmethod
    async def _enqueue(doc: Document, task: TaskSpec) -> bool:
        """入队，返回是否成功。失败时退回触发前的状态（doc 上存的仍是触发前的值）：
        任务没开始，文档本身没失败，不标 failed。
        """
        try:
            await task.enqueue(doc_id=str(doc.id))
        except Exception:
            logger.exception("文档入队失败 doc_id=%s task=%s", doc.id, task.name)
            await Document.filter(id=doc.id).update(
                status=doc.status, stage=doc.stage, error_message=doc.error_message,
            )
            return False
        return True

    async def delete(
            self, user: User, kb_id: UUID, doc_id: UUID,
    ) -> None:
        """删文档：先清 storage 对象（失败仅 log），再 ORM 级联清段/向量。"""
        doc = await self._get_user_doc(user, kb_id, doc_id)
        await self._purge_storage(doc)
        await doc.delete()  # FK CASCADE 自动清 paragraphs / embeddings

    @staticmethod
    async def _purge_storage(doc: Document) -> None:
        """清掉文档在对象存储里的全部东西：原件 + 派生目录（解析出的图）。

        失败只记日志、不抛：不阻塞 ORM 清理，用户始终能删掉记录；残留对象不影响正确性。
        """
        if doc.storage_key:
            try:
                await storage.delete(doc.storage_key)
            except Exception as e:
                logger.warning(
                    "删除原件失败 doc_id=%s key=%s: %s", doc.id, doc.storage_key, e,
                )
        prefix = build_doc_prefix(doc.knowledge_base_id, doc.id)
        try:
            await storage.delete_prefix(prefix)
        except Exception as e:
            logger.warning(
                "删除文档派生对象失败 doc_id=%s prefix=%s: %s", doc.id, prefix, e,
            )

    async def trigger_parse_many(
            self, user: User, kb_id: UUID, document_ids: list[UUID],
    ) -> tuple[list[UUID], list[UUID]]:
        return await self._trigger_many(user, kb_id, document_ids, _PARSABLE, PARSE_DOCUMENT)

    async def trigger_index_many(
            self, user: User, kb_id: UUID, document_ids: list[UUID],
    ) -> tuple[list[UUID], list[UUID]]:
        return await self._trigger_many(user, kb_id, document_ids, _INDEXABLE, INDEX_DOCUMENT)

    async def _trigger_many(
            self, user: User, kb_id: UUID, document_ids: list[UUID],
            allowed: Q, task: TaskSpec,
    ) -> tuple[list[UUID], list[UUID]]:
        """批量触发，返回 (triggered, skipped)。

        每个文档单独走「条件更新 → 入队」：Tortoise 的 update 只返回改了几行、
        不返回改了哪几行，一条语句批量改完分不清哪些是这次触发的。
        不属本库 / 不存在 / 状态不允许 / 入队失败的 id 都归 skipped。
        """
        await self._ensure_user_kb(user, kb_id)

        docs = await Document.filter(
            id__in=document_ids,
            knowledge_base_id=kb_id,
            knowledge_base__created_by=user,
        )
        claimed: set[UUID] = set()
        for doc in docs:
            if await self._claim(doc, allowed) and await self._enqueue(doc, task):
                claimed.add(doc.id)

        triggered = [did for did in document_ids if did in claimed]
        skipped = [did for did in document_ids if did not in claimed]
        return triggered, skipped

    async def delete_many(
            self, user: User, kb_id: UUID, document_ids: list[UUID],
    )-> int:
        """批量删除：先逐个清 storage 对象（失败仅 log），再一次 ORM 批量删
                （FK CASCADE 连带清段 / 向量）。返回实际删除数。
        """
        await self._ensure_user_kb(user, kb_id)

        docs = await Document.filter(
            id__in=document_ids,
            knowledge_base_id=kb_id,
            knowledge_base__created_by=user,
        )
        if not docs:
            return 0

        for doc in docs:
            await self._purge_storage(doc)
        await Document.filter(id__in=[doc.id for doc in docs]).delete()
        return len(docs)


async def get_document_service() -> DocumentService:
    return DocumentService()
