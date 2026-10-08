"""文档处理管线，分两步、各由用户触发：

- `parse_document(doc_id)`：解析 → 存图 → 组装段落落库，停在 parsed
- `index_document(doc_id)`：段落 → 子块向量 + 关键词词条，到 completed

由 SAQ worker 调用，薄封装见 `app/tasks/document_task.py`。

状态机：
- 入口前：service 已置 status=processing / stage=queued（已入队待跑）
- 处理中：解析推进 parsing → splitting，建索引为 embedding
- 完成：解析置 parsed、建索引置 completed，stage 清空
- 失败：**异常直接外抛**，不在此落库。由 tasks 层薄封装按剩余重试次数决定
  「回落 queued 等 SAQ 重试」还是「标 failed 终态」；stage 停在出错那步，
  用户重试时据此决定重做哪一步

"""

import logging
from dataclasses import replace
from io import BytesIO
from typing import NamedTuple
from uuid import UUID

from tortoise.transactions import in_transaction

from app.core.storage import storage
from app.models.knowledge import SourceType
from app.models.knowledge import (
    Document, DocStage, DocStatus, Embedding, Paragraph, ParseBackend,
)
from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter import splitter
from app.services.knowledge.parser import (
    BlockType, DocumentBlock, get_parser, strip_figure_markers,
)
from app.services.knowledge.assembler import assemble_paragraphs
from app.services.knowledge.retrieval.vector_index import ensure_hnsw_index
from app.services.knowledge.tokenization import tokenize
from app.services.model.model_client import ModelClient

logger = logging.getLogger(__name__)

# 与 Paragraph.title 的 max_length 对齐。实测本项目标题链最长 129 字、远不到上限，
# 但 PDF 那条路的层级深度未知——落库前截一刀，免得一条超长链让整份文档处理失败。
_TITLE_MAX = 256

# 删掉本次写入之外的旧向量（含上次失败留下的半截新向量）。用数组参数而非 ORM 的
# id__in：后者把每个 id 展开成一个参数，子块上万时会撞上单条语句的参数上限（32767）
_DELETE_STALE_EMBEDDINGS_SQL = (
    "DELETE FROM embeddings WHERE document_id = $1 AND id <> ALL($2::uuid[])"
)

# 关键词词条批量写回时，每条 UPDATE 带的段数（每段占 3 个参数）
_SEARCH_VECTOR_BATCH = 1000


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


async def _persist_figures(
        doc: Document, blocks: list[DocumentBlock],
) -> list[DocumentBlock]:
    """把 FIGURE 块的图字节写进对象存储，meta 里 image_bytes 换成 figure_key。

    解析器只把图裁成字节塞进 meta（见 base.py 的两阶段合同），落地到对象存储是
    管线的活——这里才有 kb_id / doc_id 拼 key，解析器拿不到也不该拿到。
    非 FIGURE 块原样放行；FIGURE 块是冻结的，用 replace 复制一份换掉 meta。
    """
    out: list[DocumentBlock] = []
    for block in blocks:
        if block.block_type is not BlockType.FIGURE:
            out.append(block)
            continue
        index = block.meta["index"]
        key = f"kb/{doc.knowledge_base_id}/doc/{doc.id}/figures/{index}.png"
        await storage.save(
            key, BytesIO(block.meta["image_bytes"]), content_type="image/png",
        )
        out.append(
            replace(
                block,
                meta={"figure_key": key, "index": index, "bbox": block.meta["bbox"]},
            )
        )
    return out


async def parse_document(doc_id: UUID) -> None:
    """第一步：解析 → 存图 → 组装段落落库，停在 parsed 等用户触发建索引。

    换段落（删旧 + 写新）与置 parsed 在同一个事务里：重新解析中途失败时，
    旧段落与旧索引原样保留，文档仍可检索。
    异常一律外抛：SAQ 靠异常判定任务失败并触发重试，失败落库由 tasks 层负责。
    """
    doc = await Document.filter(id=doc_id).prefetch_related(
        "knowledge_base",
    ).get_or_none()
    if doc is None:
        # 文档已被删；重试也变不出来，当任务正常结束，不抛
        logger.error("parse_document: 文档不存在 doc_id=%s", doc_id)
        return

    # === 解析 ===
    # status 幂等重设：service 已置 processing，此处兜底直接调用的场景
    doc.status = DocStatus.PROCESSING
    doc.stage = DocStage.PARSING
    await doc.save(update_fields=["status", "stage"])

    raw = await storage.read(doc.storage_key)
    blocks, used_backend = await _parse_with_fallback(doc, raw)
    blocks = await _persist_figures(doc, blocks)

    # === 切段 ===
    doc.stage = DocStage.SPLITTING
    await doc.save(update_fields=["stage"])

    # 标题感知组装：heading 开新段、正文并入当前段，超长在块边界续段。
    # 关键词词条不在这里算：段落此时只供预览，建索引那步才让它可检索
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
            meta={
                **({"page": d.page} if d.page is not None else {}),
                **({"figures": [dict(f) for f in d.figures]} if d.figures else {}),
            },
        )
        for i, d in enumerate(drafts)
    ]

    doc.char_length = sum(len(b.text) for b in blocks)
    doc.paragraph_count = len(paragraphs)
    doc.chunk_count = 0  # 旧向量随旧段落级联删除
    doc.status = DocStatus.PARSED
    doc.stage = DocStage.NONE
    doc.parse_backend = used_backend  # 事实，非期望：降级时与库设置不一致

    async with in_transaction() as conn:
        # 清旧 paragraphs（FK CASCADE 自动清 embeddings）
        await Paragraph.filter(document_id=doc.id).using_db(conn).delete()
        if paragraphs:
            await Paragraph.bulk_create(paragraphs, using_db=conn)
        await doc.save(
            update_fields=[
                "char_length", "paragraph_count", "chunk_count", "status", "stage",
                "parse_backend",
            ],
            using_db=conn,
        )

    logger.info(
        "parse_document doc_id=%s 完成，%d 段（解析后端 %s）",
        doc.id, len(paragraphs), used_backend,
    )


async def index_document(doc_id: UUID) -> None:
    """第二步：已落库的段落 → 子块向量 + 关键词词条，到 completed。

    先建后删：新向量逐批写入时旧向量仍在，重建期间文档照常可检索；全部写完后
    在一个事务里写关键词词条、删旧向量、置 completed。中途失败旧向量不动，
    写了一半的新向量留到重试时当作旧的一并删掉。
    异常一律外抛，失败落库由 tasks 层负责。
    """
    doc = await Document.filter(id=doc_id).prefetch_related(
        "knowledge_base",
        "knowledge_base__embedding_model",
        "knowledge_base__embedding_model__provider",
    ).get_or_none()
    if doc is None:
        # 文档已被删；重试也变不出来，当任务正常结束，不抛
        logger.error("index_document: 文档不存在 doc_id=%s", doc_id)
        return

    # status 幂等重设：service 已置 processing，此处兜底直接调用的场景
    doc.status = DocStatus.PROCESSING
    doc.stage = DocStage.EMBEDDING
    await doc.save(update_fields=["status", "stage"])

    kb = doc.knowledge_base
    chunk_cfg = ChunkConfig(**kb.chunk_config)
    paragraphs = await Paragraph.filter(document_id=doc.id).order_by("position")

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
        # 切子块算向量前抠掉图记号：子块原文落 Embedding.text、也拿去算向量，
        # 记号进这两处都是噪音；正文 content 已入库、仍留记号，不受影响
        sub_chunks = splitter.split(
            strip_figure_markers(paragraph.content), chunk_cfg
        )
        for idx, chunk_text in enumerate(sub_chunks):
            chunk_items.append(
                _ChunkItem(paragraph.id, idx, chunk_text, prefix + chunk_text)
            )

    # 写向量前确保本库的 HNSW 索引就绪：空库时建索引几乎零成本，之后的写入自动进索引
    await ensure_hnsw_index(kb.id, kb.embedding_dim)

    # 分批调 embedding（避免单次 batch 撞 API 上限）
    new_ids: list[UUID] = []
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
        new_ids.extend(e.id for e in embeddings)

    # 关键词索引抠掉图记号：记号是渲染路标，进全文检索是噪音
    for paragraph in paragraphs:
        paragraph.search_vector = tokenize(strip_figure_markers(paragraph.content))

    doc.chunk_count = len(chunk_items)
    doc.status = DocStatus.COMPLETED
    doc.stage = DocStage.NONE

    async with in_transaction() as conn:
        if paragraphs:
            await Paragraph.bulk_update(
                paragraphs, fields=["search_vector"],
                batch_size=_SEARCH_VECTOR_BATCH, using_db=conn,
            )
        await conn.execute_query(_DELETE_STALE_EMBEDDINGS_SQL, [doc.id, new_ids])
        await doc.save(update_fields=["chunk_count", "status", "stage"], using_db=conn)

    logger.info(
        "index_document doc_id=%s 完成，%d 段 / %d 子块",
        doc.id, len(paragraphs), len(chunk_items),
    )
