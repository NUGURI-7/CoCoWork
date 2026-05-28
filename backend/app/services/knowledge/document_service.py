"""Document（知识库文档）CRUD service。

只管「元数据 + storage 对象生命周期」，不含文件字节流上传（路由层的事）。
URL nested → 所有方法第一参数固定 (user, kb_id, ...)，doc_id 永远在 kb_id 之后。
可见性：用户只能操作自己创建的 KB 下的文档。
"""

import logging
from pathlib import PurePosixPath
from uuid import UUID

from app.core.config import settings
from app.core.exceptions.types import NotFound404, ValidationException
from app.core.storage import storage
from app.models.knowledge import Document, KnowledgeBase
from app.models.user import User
from app.schemas.knowledge import ALLOWED_FILE_TYPES

logger = logging.getLogger(__name__)


def _parse_file_type(name: str) -> str:
    """从文件名取小写扩展名（不带点）；无扩展名 → 空串（落白名单校验）。"""
    return PurePosixPath(name).suffix.lstrip(".").lower()


def _build_storage_key(kb_id: UUID, doc_id: UUID, file_type: str) -> str:
    """约定 `kb/{kb_id}/doc/{doc_id}.{ext}`。两后端通用（R2=对象 key，Local=相对路径）。"""
    return f"kb/{kb_id}/doc/{doc_id}.{file_type}"


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
            status="pending",
        )
        doc.storage_key = _build_storage_key(kb.id, doc.id, file_type)
        await doc.save(update_fields=["storage_key"])
        return doc

    async def list_by_kb(self, user: User, kb_id: UUID) -> list[Document]:
        """列出库下所有文档（按创建时间倒序）。"""
        await self._ensure_user_kb(user, kb_id)
        return await Document.filter(knowledge_base_id=kb_id).order_by("-created_at")

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
        doc.stage = "uploaded"
        await doc.save(update_fields=["size", "stage"])
        return doc

    async def delete(
            self, user: User, kb_id: UUID, doc_id: UUID,
    ) -> None:
        """删文档：先清 storage 对象（失败仅 log），再 ORM 级联清段/向量。"""
        doc = await self._get_user_doc(user, kb_id, doc_id)

        if doc.storage_key:
            try:
                await storage.delete(doc.storage_key)
            except Exception as e:
                # 不阻塞 ORM 清理：用户始终能清掉记录，孤儿对象交给桶生命周期
                logger.warning(
                    "删除 storage 对象失败 doc_id=%s key=%s: %s",
                    doc.id, doc.storage_key, e,
                )

        await doc.delete()  # FK CASCADE 自动清 paragraphs / embeddings


async def get_document_service() -> DocumentService:
    return DocumentService()
