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
from typing import NamedTuple
from uuid import UUID

from app.core.storage import storage
from app.models.knowledge import SourceType
from app.models.knowledge import (
    Document, DocStage, DocStatus, Embedding, Paragraph, ParseBackend,
)
from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter import splitter
from app.services.knowledge.parser import DocumentBlock, get_parser
from app.services.knowledge.assembler import assemble_paragraphs
from app.services.knowledge.tokenization import tokenize
from app.services.model.model_client import ModelClient

logger = logging.getLogger(__name__)

# 与 Paragraph.title 的 max_length 对齐。实测本项目标题链最长 129 字、远不到上限，
# 但 PDF 那条路的层级深度未知——落库前截一刀，免得一条超长链让整份文档处理失败。
_TITLE_MAX = 256


class _ChunkItem(NamedTuple):
    """一个待 embed 的子块。

    `text` 与 `embed_text` **刻意分开**：前者落库（`Embedding.text` = 子块
    原文，命中后展示「命中了哪一小段」用），后者送去算向量（可能前置了段的
    标题链）。两者不相等是有意为之，不是 bug。
    """

    paragraph_id: UUID
    position: int
    text: str
    embed_text: str


async def _parse_with_fallback(
        doc: Document, raw: bytes,
) -> tuple[list[DocumentBlock], ParseBackend]:
    """按库设置解析；云端路失败则退回本地。返回块列表与**实际**用的后端。

    降级而非直接失败，是因为「有内容」比「整份处理失败」有用。但降级后表格与
    三四级标题都没了，所以实际后端必须记回 `Document.parse_backend` —— 用户
    得看得见这份文档的质量打过折，才知道该不该重跑。静默降级比失败更糟。
    """
    wanted_backend = doc.knowledge_base.parse_backend
    try:
        blocks = await get_parser(doc.file_type, wanted_backend).parse(raw)
        return blocks, wanted_backend
    except Exception:
        if wanted_backend is ParseBackend.LOCAL:
            # 本地路就是兜底本身，它炸了没有下一层可退 —— 照常抛给任务层重试
            raise
        # 抓得宽是有意的：网络 / 鉴权 / 超时，任何原因导致云端没结果，处置都一样。
        # 细分错误类型的价值在「要不要重试」，而重试这件事已经决定不做了。
        # 用 exception 而非 warning：降级是静默发生的，traceback 是事后唯一的线索
        logger.exception(
            "云端解析失败，降级本地 doc_id=%s backend=%s", doc.id, wanted_backend,
        )

    blocks = await get_parser(doc.file_type, ParseBackend.LOCAL).parse(raw)
    return blocks, ParseBackend.LOCAL


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
    blocks, used_backend = await _parse_with_fallback(doc, raw)

    # === 切段 ===
    doc.stage = DocStage.SPLITTING
    await doc.save(update_fields=["stage"])

    # 重入：清旧 paragraphs（FK CASCADE 自动清 embeddings）
    await Paragraph.filter(document_id=doc.id).delete()

    # 标题感知组装：heading 开新段、正文并入当前段，超长在块边界续段
    drafts = assemble_paragraphs(blocks)
    paragraphs = [
        Paragraph(
            knowledge_base_id=doc.knowledge_base_id,
            document_id=doc.id,
            content=d.content,
            title=d.title[:_TITLE_MAX],
            position=i,
            char_length=len(d.content),
            # 页码只有 PDF 有。没有时给空 dict 而不是 {"page": None}——
            # 免得下游要分「没这个键」和「键在但值是 null」两种情况
            meta={"page": d.page} if d.page is not None else {},
            search_vector=tokenize(d.content),
        )
        for i, d in enumerate(drafts)
    ]
    if paragraphs:
        await Paragraph.bulk_create(paragraphs)

    # === 切块 + Embedding ===
    doc.stage = DocStage.EMBEDDING
    await doc.save(update_fields=["stage"])

    kb =  doc.knowledge_base
    chunk_cfg = ChunkConfig(**kb.chunk_config)

    # 汇总所有段的子块
    chunk_items: list[_ChunkItem] = []
    for paragraph in paragraphs:
        # 标题链前置：段的 content 只带**直接那级**标题，切成子块后连这个都
        # 可能没有——「不超过 30 天」脱离「第三章 > 报销流程」检索时就比不中。
        # 形态同 LlamaIndex 的 MetadataMode.EMBED / Anthropic Contextual Retrieval。
        # 段内所有子块共用同一前缀，故在内层循环外算一次。
        prefix = (
            f"{paragraph.title}\n\n"
            if chunk_cfg.prepend_title and paragraph.title
            else ""
        )
        sub_chunks = splitter.split(paragraph.content, chunk_cfg)
        for idx, chunk_text in enumerate(sub_chunks):
            chunk_items.append(
                _ChunkItem(paragraph.id, idx, chunk_text, prefix + chunk_text)
            )

    # 分批调 embedding（避免单次 batch 撞 API 上限）
    BATCH = 32
    for start in range(0,len(chunk_items), BATCH):
        batch = chunk_items[start: start + BATCH]

        # 送去算向量的是 embed_text（含标题链），落库的是 text（子块原文）
        vectors = await ModelClient.create_embedding(
            kb.embedding_model, [c.embed_text for c in batch],
        )
        embeddings = [
                Embedding(
                    knowledge_base_id = kb.id,
                    document_id=doc.id,
                    paragraph_id=c.paragraph_id,
                    source_type=SourceType.CONTENT,
                    text=c.text,
                    position=c.position,
                    embedding=vector
                )
            for c, vector in zip(batch, vectors)
        ]
        await Embedding.bulk_create(embeddings)

    # === 收尾 ===
    doc.char_length = sum(len(b.text) for b in blocks)
    doc.paragraph_count = len(paragraphs)
    doc.chunk_count = len(chunk_items)
    doc.status = DocStatus.COMPLETED
    doc.stage = DocStage.NONE
    doc.parse_backend = used_backend  # 事实，非期望：降级时与库设置不一致

    await doc.save(update_fields=[
        "char_length", "paragraph_count", "chunk_count", "status", "stage",
        "parse_backend",
    ])

    logger.info(
        "process_document doc_id=%s 完成，%d 段 / %d 子块（解析后端 %s）",
        doc.id, len(paragraphs), len(chunk_items), used_backend,
    )