"""Rerank 两级管线冒烟脚本（一次性实验脚本，不进产品）。

绕过 HTTP / 认证，直接打 RetrievalService：同一条 query 跑两遍
（不带 / 带 rerank）并排打印，肉眼比对精排分数、排序变化与耗时。

用法（在 backend/ 目录下）::

    uv run python -m scripts.smoke_rerank \\
        --kb <KB id 或库名> --query "库里有答案的真问题"
"""

import argparse
import asyncio
from uuid import UUID

from app.db.postgresql import pg_client
from app.services.knowledge.retrieval.base import RetrievalMode, RetrievalParams
from app.services.knowledge.retrieval.service import RetrievalService
from benchmarks.import_corpus import _resolve_kb


def _fmt_hits(hits) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        content = h.content.replace("\n", " ")[:36]
        via = h.matched_by or "-"
        lines.append(f"  {i}. score={h.score:.4f}  via={via:<7}  {content}")
    return "\n".join(lines) if lines else "  （无命中）"


async def _run(svc: RetrievalService, user, kb_id, params: RetrievalParams, label: str):
    result = await svc.retrieve(user, kb_id, params)
    t = result.timings
    print(f"\n== {label} ==")
    print(_fmt_hits(result.hits))
    print(f"  timings: total={t.get('total_ms', 0)}ms  rerank={t.get('rerank_ms', 0)}ms")


async def main() -> None:
    parser = argparse.ArgumentParser(description="rerank 两级管线冒烟对比")
    parser.add_argument("--kb", required=True, help="KB id 或库名")
    parser.add_argument("--query", required=True, help="测试问题（库里应有答案）")
    parser.add_argument(
        "--rerank-model",
        default="019f7b4a-2076-7391-910b-12c11cbc6a4b",
        help="rerank 模型 id（默认 = 硅基流动 bge-reranker-v2-m3 实例）",
    )
    parser.add_argument("--mode", default="hybrid", choices=[m.value for m in RetrievalMode])
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    await pg_client.connect()
    try:
        kb = await _resolve_kb(args.kb)
        # 归属校验要 User 实例：直接用库主本人，保证 KB / rerank 模型同主可查
        await kb.fetch_related("created_by")
        user = kb.created_by
        svc = RetrievalService()

        base = dict(query=args.query, mode=RetrievalMode(args.mode), top_k=args.top_k)
        await _run(svc, user, kb.id, RetrievalParams(**base), f"对照组：{args.mode} 单级")
        await _run(
            svc, user, kb.id,
            RetrievalParams(**base, rerank_model_id=UUID(args.rerank_model)),
            f"两级：{args.mode} + rerank",
        )
    finally:
        await pg_client.close()


if __name__ == "__main__":
    asyncio.run(main())
