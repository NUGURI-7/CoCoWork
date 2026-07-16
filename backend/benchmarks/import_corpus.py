"""Multi-CPR 医疗语料导入脚本（检索基准配套，不进产品）。

两阶段（先入库、后加工，可分别断点续跑）：
- ``import``：TSV → Paragraph 纯落库，不碰 embedding API；
- ``embed``：扫「还没向量的段」，按库配置切子块（复用产品 splitter，
  与正式处理管线同款），分批调 embedding 补 Embedding 行（一段 N 块）。

用法（在 backend/ 目录下）::

    uv run python -m benchmarks.import_corpus import \\
        --kb 医疗检索基准 --file ../data/medical/corpus_split_1.tsv --limit 10000
    uv run python -m benchmarks.import_corpus embed --kb 医疗检索基准 --workers 4

断点续传：
- ``import``：文件行序固定 + 每批一个事务（不存在半批脏数据），
  「该 Document 名下已有的段数」即已消费行数，启动时 count 后跳行接灌；
- ``embed``：「没有 Embedding 的 Paragraph」本身就是待办清单，天然精确断点。

pid 存两处：``Paragraph.title``（embed 阶段回查 + UI 可见）与
``Embedding.meta["pid"]``（评测脚本对 qrels 用）。
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from uuid import UUID

from tortoise.transactions import in_transaction

from app.db.postgresql import pg_client
from app.models.knowledge import (
    DocStatus,
    Document,
    Embedding,
    KnowledgeBase,
    Paragraph,
    SourceType,
)
from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter import splitter
from app.services.model.model_client import ModelClient

logger = logging.getLogger(__name__)

# 硅基流动 embeddings 接口单次上限 32 条，与 document_processor 保持一致
EMBED_BATCH = 32
# import 阶段纯 DB 写入，批次可以大得多
INSERT_BATCH = 1000
# embedding API 失败重试
EMBED_RETRIES = 3


# ---------------------------------------------------------------- 公共

async def _resolve_kb(kb_ref: str) -> KnowledgeBase:
    """按 UUID 或库名找 KB（同名多库时报错让用户改用 UUID）。"""
    try:
        kb_id = UUID(kb_ref)
        kb = await KnowledgeBase.filter(id=kb_id).prefetch_related(
            "embedding_model", "embedding_model__provider",
        ).get_or_none()
        if kb is None:
            raise SystemExit(f"知识库不存在：{kb_ref}")
        return kb
    except ValueError:
        pass

    kbs = await KnowledgeBase.filter(name=kb_ref).prefetch_related(
        "embedding_model", "embedding_model__provider",
    )
    if not kbs:
        raise SystemExit(f"知识库不存在：{kb_ref}")
    if len(kbs) > 1:
        ids = "\n".join(f"  {kb.id}" for kb in kbs)
        raise SystemExit(f"同名知识库有 {len(kbs)} 个，请改用 --kb <UUID>：\n{ids}")
    return kbs[0]


def _parse_line(line: str, line_no: int) -> tuple[int, str]:
    """解析 TSV 一行 → (pid, text)。格式坏了直接 fail fast，报行号。"""
    parts = line.rstrip("\n").split("\t", 1)
    if len(parts) != 2 or not parts[1].strip():
        raise SystemExit(f"TSV 第 {line_no} 行格式异常：{line[:80]!r}")
    return int(parts[0]), parts[1].strip()


class _Progress:
    """控制台进度：每批打一行「已完成/总数、百分比、速度、预计剩余」。"""

    def __init__(self, label: str, total: int, done: int = 0):
        self.label = label
        self.total = total
        self.start_done = done
        self.done = done
        self.start_at = time.monotonic()

    def advance(self, n: int) -> None:
        self.done += n
        elapsed = time.monotonic() - self.start_at
        rate = (self.done - self.start_done) / elapsed if elapsed > 0 else 0.0
        remain = (self.total - self.done) / rate if rate > 0 else 0.0
        print(
            f"[{self.label}] {self.done:,}/{self.total:,}"
            f" ({self.done / self.total:.1%})"
            f" — {rate:,.0f} 条/秒 — 预计剩余 {remain / 60:.1f} 分钟",
            flush=True,
        )


# ---------------------------------------------------------------- import 阶段

async def cmd_import(kb_ref: str, file: str, limit: int | None) -> None:
    """TSV → Paragraph 纯落库（pid 存 title），每批一个事务。"""
    path = Path(file)
    if not path.is_file():
        raise SystemExit(f"文件不存在：{path}")

    kb = await _resolve_kb(kb_ref)

    doc, created = await Document.get_or_create(
        knowledge_base=kb,
        name=path.name,
        defaults={
            "file_type": "txt",
            "size": path.stat().st_size,
            "storage_key": f"benchmark/{path.name}",
            "status": DocStatus.COMPLETED,
        },
    )
    print(f"Document「{doc.name}」{'新建' if created else '已存在'}（id={doc.id}）")

    with path.open(encoding="utf-8") as f:
        total_lines = sum(1 for _ in f)
    target = min(limit, total_lines) if limit else total_lines

    done = await Paragraph.filter(document_id=doc.id).count()
    if done >= target:
        print(f"已入库 {done:,} 段 ≥ 目标 {target:,}，无需导入")
        return
    if done:
        print(f"断点续传：已入库 {done:,} 段，从第 {done + 1:,} 行接着灌")

    progress = _Progress("import", target, done)
    batch: list[Paragraph] = []

    async def flush() -> None:
        nonlocal batch
        if not batch:
            return
        async with in_transaction():
            await Paragraph.bulk_create(batch)
        progress.advance(len(batch))
        batch = []

    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if line_no <= done:
                continue
            if line_no > target:
                break
            pid, text = _parse_line(line, line_no)
            batch.append(Paragraph(
                knowledge_base_id=kb.id,
                document_id=doc.id,
                content=text,
                title=str(pid),
                position=line_no - 1,
                char_length=len(text),
            ))
            if len(batch) >= INSERT_BATCH:
                await flush()
    await flush()

    doc.paragraph_count = await Paragraph.filter(document_id=doc.id).count()
    doc.char_length = doc.size
    await doc.save(update_fields=["paragraph_count", "char_length"])
    print(f"完成：Document「{doc.name}」共 {doc.paragraph_count:,} 段")


# ---------------------------------------------------------------- embed 阶段

async def _embed_with_retry(kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    """embedding API 调用，指数退避重试。"""
    for attempt in range(EMBED_RETRIES):
        try:
            return await ModelClient.create_embedding(kb.embedding_model, texts)
        except Exception:
            if attempt == EMBED_RETRIES - 1:
                raise
            wait = 2 ** (attempt + 1)
            logger.warning("embedding 调用失败，%ds 后重试", wait, exc_info=True)
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")


async def _embed_group(
    kb: KnowledgeBase,
    group: list[tuple[Paragraph, list[str]]],
) -> None:
    """一组「段 + 其子块」：调 embedding → 同事务落全部 Embedding 行。

    断点判定是「段有没有向量」，所以一段的全部子块必须同事务写入，
    不允许出现半段。组内块数由调用方打包控制在 ≤ EMBED_BATCH，
    这里仍按 32 切 API 子批兜底（防单段块数异常多）。
    """
    items = [
        (p, idx, chunk)
        for p, chunks in group
        for idx, chunk in enumerate(chunks)
    ]
    vectors: list[list[float]] = []
    for start in range(0, len(items), EMBED_BATCH):
        texts = [chunk for _, _, chunk in items[start:start + EMBED_BATCH]]
        vectors.extend(await _embed_with_retry(kb, texts))

    rows = [
        Embedding(
            knowledge_base_id=kb.id,
            document_id=p.document_id,
            paragraph_id=p.id,
            source_type=SourceType.CONTENT,
            text=chunk,
            position=idx,
            embedding=vector,
            meta={"pid": int(p.title)},
        )
        for (p, idx, chunk), vector in zip(items, vectors, strict=True)
    ]
    async with in_transaction():
        await Embedding.bulk_create(rows)


def _pack_groups(
    paragraphs: list[Paragraph], chunk_cfg: ChunkConfig,
) -> list[list[tuple[Paragraph, list[str]]]]:
    """段切块后按「组内块数总和 ≤ EMBED_BATCH」打包，一组 = 一次 API 调用。"""
    groups: list[list[tuple[Paragraph, list[str]]]] = []
    cur: list[tuple[Paragraph, list[str]]] = []
    cur_chunks = 0
    for p in paragraphs:
        chunks = splitter.split(p.content, chunk_cfg) or [p.content]
        if cur and cur_chunks + len(chunks) > EMBED_BATCH:
            groups.append(cur)
            cur, cur_chunks = [], 0
        cur.append((p, chunks))
        cur_chunks += len(chunks)
    if cur:
        groups.append(cur)
    return groups


async def cmd_embed(kb_ref: str, workers: int, reset: bool) -> None:
    """扫「没向量的段」，切块 → 分批补 Embedding，workers 组并发调 API。"""
    kb = await _resolve_kb(kb_ref)
    chunk_cfg = ChunkConfig(**kb.chunk_config)

    if reset:
        deleted = await Embedding.filter(knowledge_base_id=kb.id).delete()
        print(f"--reset：已清掉旧向量 {deleted:,} 条")

    pending_q = Paragraph.filter(knowledge_base_id=kb.id, embeddings__isnull=True)
    total = await pending_q.count()
    if total == 0:
        print("没有待向量化的段，全部完成")
        return
    print(
        f"待向量化 {total:,} 段"
        f"（切块 {chunk_cfg.chunk_size}/{chunk_cfg.overlap}，"
        f"每批 {EMBED_BATCH} 块 × {workers} 并发）"
    )

    progress = _Progress("embed", total)
    while True:
        paragraphs = await pending_q.limit(EMBED_BATCH * workers)
        if not paragraphs:
            break
        groups = _pack_groups(paragraphs, chunk_cfg)
        for start in range(0, len(groups), workers):
            await asyncio.gather(
                *(_embed_group(kb, g) for g in groups[start:start + workers])
            )
        progress.advance(len(paragraphs))

    # 回写各 Document 的块数冗余字段
    async for doc in Document.filter(knowledge_base_id=kb.id):
        doc.chunk_count = await Embedding.filter(document_id=doc.id).count()
        await doc.save(update_fields=["chunk_count"])
    print("向量化完成")


# ---------------------------------------------------------------- 入口

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-CPR 语料导入（基准实验设施）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="TSV → Paragraph 纯落库")
    p_import.add_argument("--kb", required=True, help="知识库 UUID 或库名")
    p_import.add_argument("--file", required=True, help="corpus TSV 路径")
    p_import.add_argument("--limit", type=int, default=None, help="只导入前 N 行")

    p_embed = sub.add_parser("embed", help="切块 + 补向量（断点自动接续）")
    p_embed.add_argument("--kb", required=True, help="知识库 UUID 或库名")
    p_embed.add_argument("--workers", type=int, default=4, help="并发组数（每组 32 块）")
    p_embed.add_argument("--reset", action="store_true", help="先清掉库里全部旧向量再跑")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await pg_client.connect()
    try:
        if args.command == "import":
            await cmd_import(args.kb, args.file, args.limit)
        else:
            await cmd_embed(args.kb, args.workers, args.reset)
    finally:
        await pg_client.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _build_parser().parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\n已中断——进度都在库里，重跑同一条命令即可续传", file=sys.stderr)


if __name__ == "__main__":
    main()
