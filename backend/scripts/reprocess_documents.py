"""批量重新处理文档：按当前的解析 / 切块规则重建段与向量。

改了 parser / assembler 之后，已入库的文档仍是**旧规则切出来的**，必须重跑
才生效。`process_document` 本身可重入（先清掉该文档的旧段，FK CASCADE 连带
清向量），故直接逐个调即可。

**默认 dry-run**，只列出会动谁；加 `--apply` 才真的写。

不走 SAQ 队列而是直接调：批量重跑是一次性运维动作，要的是「看得见进度、
失败当场知道是哪个文档」；入队则要盯 worker 日志，且 43 个任务混在业务队列里
会挤掉正常的上传处理。

    uv run python scripts/reprocess_documents.py                    # 看会动谁
    uv run python scripts/reprocess_documents.py --kb 测试 --apply   # 先拿一个库探路
    uv run python scripts/reprocess_documents.py --apply            # 全量
"""

import argparse
import asyncio
import time
from uuid import UUID

from app.db.postgresql import PostgreSQLClient
from app.models.knowledge import Document, DocStatus, Paragraph
from app.services.knowledge.document_processor import process_document

# 排除的知识库（名称精确匹配）。**动它们是数据损失，不是重算**：
# 1. 两个库都是 txt 语料，`title` 由导入脚本从语料字段填入；txt 解析路径根本
#    产不出标题，重跑一遍 10000 段的 title 全变空串。
# 2. rerank 否决、hybrid 五点扫描等历史结论全跑在它们身上，切分一变，
#    `benchmarks/FINDINGS.md` 里的数字就失去可比性。
EXCLUDED_KBS = ("医疗检索基准", "电商检索基准")

# 与 document_processor 的 BATCH 对齐，仅用于 dry-run 时估算调用量
EMBED_BATCH = 32


async def _snapshot(doc_id: UUID) -> tuple[int, int]:
    """取某文档当前的 (段数, 有标题链的段数)。"""
    total = await Paragraph.filter(document_id=doc_id).count()
    titled = await Paragraph.filter(document_id=doc_id).exclude(title="").count()
    return total, titled


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="按当前解析 / 切块规则重新处理文档（默认 dry-run）"
    )
    parser.add_argument("--apply", action="store_true", help="真正执行；不加则只列出计划")
    parser.add_argument("--kb", help="只处理指定知识库（名称精确匹配）")
    parser.add_argument("--limit", type=int, help="最多处理几个，先跑一两个探路用")
    args = parser.parse_args()

    client = PostgreSQLClient()
    await client.connect()
    try:
        query = Document.all().prefetch_related("knowledge_base")
        if args.kb:
            query = query.filter(knowledge_base__name=args.kb)

        docs = [
            d for d in await query.order_by("created_at")
            if d.knowledge_base.name not in EXCLUDED_KBS
        ]
        if args.limit:
            docs = docs[: args.limit]

        if not docs:
            print("没有匹配的文档。")
            return

        # --- 计划 ---
        print(f"目标 {len(docs)} 个文档：\n")
        for d in docs:
            print(f"  [{d.knowledge_base.name:<22}] {d.name:<40} "
                  f"{d.file_type:<4} {d.paragraph_count or 0:>4} 段 / {d.chunk_count or 0:>4} 子块")

        chunks = sum(d.chunk_count or 0 for d in docs)
        print(f"\n合计 {chunks} 子块 → 约 {-(-chunks // EMBED_BATCH)} 次 embedding 批调用")
        print(f"排除的知识库：{', '.join(EXCLUDED_KBS)}")

        if not args.apply:
            print("\n--- dry-run，未写入任何数据。确认无误后加 --apply ---")
            return

        # --- 执行 ---
        print("\n开始重新处理：\n")
        failed: list[tuple[Document, Exception]] = []
        t_all = time.perf_counter()

        for i, doc in enumerate(docs, 1):
            before, _ = await _snapshot(doc.id)
            t0 = time.perf_counter()
            try:
                await process_document(doc.id)
            except Exception as e:
                # 直接调用没有 SAQ 的重试机制，故一次失败即标终态，
                # 与 document_task.py「重试用尽」那一支一致；不中断整批。
                failed.append((doc, e))
                await Document.filter(id=doc.id).update(
                    status=DocStatus.FAILED,
                    error_message=f"{type(e).__name__}: {e}",
                )
                print(f"  [{i}/{len(docs)}] ❌ {doc.name}  {type(e).__name__}: {e}")
                continue

            after, titled = await _snapshot(doc.id)
            print(f"  [{i}/{len(docs)}] ✅ {doc.name:<40} "
                  f"{before:>4} → {after:<4} 段，有标题链 {titled:>4}/{after:<4} "
                  f"{time.perf_counter() - t0:>5.1f}s")

        # --- 汇总 ---
        elapsed = time.perf_counter() - t_all
        print(f"\n完成 {len(docs) - len(failed)}/{len(docs)}，总耗时 {elapsed:.1f}s")
        if failed:
            print("\n失败清单：")
            for d, e in failed:
                print(f"  [{d.knowledge_base.name}] {d.name}: {type(e).__name__}: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
