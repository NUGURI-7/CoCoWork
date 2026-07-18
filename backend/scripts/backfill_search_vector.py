"""存量段落 search_vector 回填脚本（一次性运维工具）。

``Paragraph.search_vector`` 列是后加的（迁移 0013/0014），存量段全是 NULL。
本脚本扫「search_vector IS NULL」的段，用产品同款 tokenizer 分词回填。

- 待办清单 = IS NULL 本身：中断重跑即续传，无需额外进度状态
  （与 import_corpus 的 embed 阶段同一哲学）；
- 不区分知识库，全库通吃（基准语料 + 产品库一起补齐）；
- 分词口径变更后重灌：先手动 ``UPDATE paragraphs SET search_vector = NULL``
  再跑本脚本即可。

用法（在 backend/ 目录下）::

    uv run python -m scripts.backfill_search_vector
"""

import asyncio
import logging
import sys
import time

from app.db.postgresql import pg_client
from app.models.knowledge import Paragraph
from app.services.knowledge.tokenization import tokenize

logger = logging.getLogger(__name__)

# 纯 DB 读写 + 本地 CPU 分词，批次大小只受单条 UPDATE 语句体积约束
BATCH = 500


async def backfill() -> None:
    total = await Paragraph.filter(search_vector__isnull=True).count()
    if total == 0:
        print("没有待回填的段落，收工")
        return
    print(f"待回填 {total} 段")

    done = 0
    started = time.monotonic()
    while True:
        batch = await (
            Paragraph.filter(search_vector__isnull=True)
            .limit(BATCH)
            .only("id", "content")
        )
        if not batch:
            break
        for paragraph in batch:
            paragraph.search_vector = tokenize(paragraph.content)
        await Paragraph.bulk_update(batch, fields=["search_vector"])
        done += len(batch)
        rate = done / (time.monotonic() - started)
        print(f"  {done}/{total} 段（{rate:.0f} 段/秒）")

    print("回填完成")


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
        print("\n已中断——IS NULL 就是待办清单，重跑同一条命令即可续传", file=sys.stderr)


if __name__ == "__main__":
    main()
