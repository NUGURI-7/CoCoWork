"""存量知识库 HNSW 索引补建脚本（一次性运维工具）。

HNSW 部分索引原本只在文档写向量前按库建（``ensure_hnsw_index``），
此前建的库从没建过。本脚本逐库调用同一个函数补齐：

- 已有可用索引的库跳过，中断重跑即续传，无需额外进度状态；
- 超过维度上限的库只打日志、不建；
- 索引按标准名识别（``hnsw_index_name``），名字不合规的手工索引会被视为不存在、重复建一条，
  执行前先把它们改成标准名。

用法（在 backend/ 目录下）::

    uv run python -m scripts.backfill_hnsw_indexes
"""

import asyncio
import logging
import sys
import time

from app.db.postgresql import pg_client
from app.models.knowledge import KnowledgeBase
from app.services.knowledge.retrieval.vector_index import ensure_hnsw_index

logger = logging.getLogger(__name__)


async def backfill() -> None:
    kbs = await KnowledgeBase.all().only("id", "name", "embedding_dim").order_by("created_at")
    print(f"共 {len(kbs)} 个知识库")

    for i, kb in enumerate(kbs, 1):
        started = time.monotonic()
        await ensure_hnsw_index(kb.id, kb.embedding_dim)
        print(f"  [{i}/{len(kbs)}] {kb.name}（{kb.id}）{time.monotonic() - started:.1f}s")

    print("补建完成")


async def _run() -> None:
    await pg_client.connect()
    try:
        await backfill()
    finally:
        await pg_client.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n已中断——已建好的索引会被跳过，重跑同一条命令即可续传", file=sys.stderr)


if __name__ == "__main__":
    main()
