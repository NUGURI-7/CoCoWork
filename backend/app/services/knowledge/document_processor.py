"""文档处理管线主函数。

入口 `process_document(doc_id)`：解析→切段→切块→embed→更新状态。
由 SAQ worker 调用，薄封装见 `app/tasks/document_task.py`。

状态机：
- 入口前：service 已置 status=processing / stage=queued（已入队待跑）
- 处理中：stage 跟着推进 parsing/splitting/embedding
- 完成：status=completed，stage 清空
- 失败：**异常直接外抛**，不在此落库。由 tasks 层薄封装按剩余重试次数决定
  「回落 queued 等 SAQ 重试」还是「标 failed 终态」

"""

import logging
from uuid import UUID

from app.core.storage import storage
from app.models.knowledge import SourceType
from app.models.knowledge import Document, DocStage, DocStatus, Embedding, Paragraph
from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter import splitter
from app.services.knowledge.tokenization import tokenize
from app.services.model.model_client import ModelClient

logger = logging.getLogger(__name__)


def _split_paragraphs(text: str) -> list[str]:
    """按双换行切段，strip + 过滤空段；没双换行整文 1 段。"""
    return [ p.strip() for p in text.split("\n\n") if p.strip()]



async def process_document(doc_id: UUID) -> None:
    """文档处理入口。

        异常一律外抛：SAQ 靠异常判定任务失败并触发重试，失败落库统一由
        tasks 层薄封装负责，此处不吞异常。
    """

    doc = await Document.filter(id=doc_id).prefetch_related(
        "knowledge_base",
        "knowledge_base__embedding_model",
        "knowledge_base__embedding_model__provider",
    ).get_or_none()
    if doc is None:
        # 文档已被删；重试也变不出来，当任务正常结束，不抛
        logger.error("process_document: 文档不存在 doc_id=%s", doc_id)
        return

    # === 解析 ===
    # status 幂等重设：service 已置 processing，此处兜底直接调用的场景
    doc.status = DocStatus.PROCESSING
    doc.stage = DocStage.PARSING
    await doc.save(update_fields=["status","stage"])

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
            search_vector=tokenize(p),
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