"""文档处理管线主函数。

入口 `process_document(doc_id)`：解析→切段→切块→embed→更新状态。
v1 由 BackgroundTasks 调（同步在 web 进程内跑），将来切 ARQ 只换调用处。

状态机：
- 入口前：stage=uploaded（首次）或 status=failed（重试）
- 处理中：status=processing，stage 跟着推进 parsing/splitting/embedding
- 完成：status=completed
- 失败：status=failed + error_message 记原因，stage 留在出错那步

"""

import logging
from uuid import UUID

from app.core.storage import storage
from app.models.knowledge import SourceType
from app.models.knowledge import Document, DocStage, DocStatus, Embedding, Paragraph
from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter import splitter
from app.services.model.model_client import ModelClient

logger = logging.getLogger(__name__)


def _split_paragraphs(text: str) -> list[str]:
    """按双换行切段，strip + 过滤空段；没双换行整文 1 段。"""
    return [ p.strip() for p in text.split("\n\n") if p.strip()]



async def process_document(doc_id: UUID) -> None:
    """文档处理入口。

        捕全部异常 → status=failed 落库（BackgroundTasks 不会传播异常，得自己消化）。
    """

    doc = await Document.filter(id=doc_id).prefetch_related(
        "knowledge_base",
        "knowledge_base__embedding_model",
        "knowledge_base__embedding_model__provider",
    ).get_or_none()
    if doc is None:
        logger.error("process_document: 文档不存在 doc_id=%s", doc_id)
        return

    try:
        # === 解析 ===
        doc.status = DocStatus.PROCESSING
        doc.stage = DocStage.PARSING
        doc.error_message = ""
        await doc.save(update_fields=["status","stage","error_message"])

        raw = await storage.read(doc.storage_key)
        text = raw.decode("utf-8")

        # === 切段 ===
        doc.stage = DocStage.SPLITTING
        await doc.save(update_fields=["stage"])

        # 重入：清旧 paragraphs（FK CASCADE 自动清 embeddings）
        await Paragraph.filter(document_id=doc.id).delete()

        para_texts = _split_paragraphs(text)
        paragraphs = [
            Paragraph(
                knowledge_base_id=doc.knowledge_base_id,
                document_id=doc.id,
                content=p,
                position=i,
                char_length=len(p),
            )
            for i,p in enumerate(para_texts)
        ]
        if paragraphs:
            await Paragraph.bulk_create(paragraphs)

        # === 切块 + Embedding ===
        doc.stage = DocStage.EMBEDDING
        await doc.save(update_fields=["stage"])

        kb =  doc.knowledge_base
        chunk_cfg = ChunkConfig(**kb.chunk_config)

        # 汇总所有段的子块 [(paragraph_id, position, text), ...]
        chunk_items: list[tuple] = []
        for paragraph in paragraphs:
            sub_chunks = splitter.split(paragraph.content,chunk_cfg)
            for idx, chunk_text in enumerate(sub_chunks):
                chunk_items.append((paragraph.id, idx, chunk_text))

        # 分批调 embedding（避免单次 batch 撞 API 上限）
        BATCH = 32
        for start in range(0,len(chunk_items), BATCH):
            batch = chunk_items[start: start + BATCH]
            texts = [item[2] for item in batch]

            vectors = await ModelClient.create_embedding(
                kb.embedding_model, texts,
            )
            embeddings = [
                    Embedding(
                        knowledge_base_id = kb.id,
                        document_id=doc.id,
                        paragraph_id=pid,
                        source_type=SourceType.CONTENT,
                        text=text,
                        position=pos,
                        embedding=vector
                    )
                for (pid, pos, text),vector in zip(batch, vectors)
            ]
            await Embedding.bulk_create(embeddings)

        # === 收尾 ===
        doc.char_length = len(text)
        doc.paragraph_count = len(paragraphs)
        doc.chunk_count = len(chunk_items)
        doc.status = DocStatus.COMPLETED
        doc.stage = DocStage.NONE

        await doc.save(update_fields=[
            "char_length", "paragraph_count", "chunk_count", "status", "stage",
        ])

        logger.info(
            "process_document doc_id=%s 完成，%d 段 / %d 子块",
            doc.id, len(paragraphs), len(chunk_items),
        )

    except Exception as e:
        logger.exception("process_document 失败 doc_id=%s", doc_id)
        doc.status = DocStatus.FAILED
        doc.error_message = f"{type(e).__name__}: {e}"
        await doc.save(update_fields=["status", "error_message"])





















