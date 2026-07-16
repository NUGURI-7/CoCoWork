"""检索召回 / 延迟评测脚本（检索基准配套，不进产品）。

拿 Multi-CPR 的 dev query + qrels 考产品检索链路（VectorRetriever 原样复用，
测的就是产品真实路径）：每条 query 走一次检索 → 命中段查回 pid → 与 qrels
对分。指标交给 ranx（recall@k / MRR@k），延迟取 retriever 自带的
embed_ms / search_ms 埋点分位数。

用法（在 backend/ 目录下）::

    uv run python -m benchmarks.eval_recall --kb 医疗检索基准 \\
        --queries ../data/medical/dev.query.txt \\
        --qrels ../data/medical/qrels.dev.tsv

- ``--limit``：只跑前 N 条 query（快速冒烟）
- ``--top-k``：召回深度（默认 10，即 recall@10 / mrr@10）
- 标准答案不在库里的 query 自动跳过并报数（小规模导入时防止分数被冤枉拉低）
- 顺序执行不并发：并发会互相挤占，把延迟分位数搞脏
"""

import argparse
import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from ranx import Qrels, Run, evaluate
from tortoise import connections
from tortoise.transactions import in_transaction

from app.db.postgresql import pg_client
from app.models.knowledge import Paragraph
from app.services.knowledge.retrieval.base import RetrievalParams
from app.services.knowledge.retrieval.sql import load_sql
from app.services.knowledge.retrieval.vector import (
    CANDIDATE_FACTOR,
    VectorRetriever,
    _to_vector_literal,
)
from app.services.model import ModelClient
from benchmarks.import_corpus import _resolve_kb


def _load_queries(path: Path) -> dict[str, str]:
    """dev.query.txt：``qid⇥text`` → {qid: text}。"""
    queries: dict[str, str] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            qid, text = line.rstrip("\n").split("\t", 1)
            queries[qid] = text.strip()
    return queries


def _load_qrels(path: Path) -> dict[str, dict[str, int]]:
    """qrels.dev.tsv：``qid 0 pid rel`` → {qid: {pid: rel}}。"""
    qrels: dict[str, dict[str, int]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            qid, _, pid, rel = line.split()
            qrels.setdefault(qid, {})[pid] = int(rel)
    return qrels


def _percentiles(values: list[float]) -> dict[str, float]:
    """延迟分位数 {p50, p95, p99}（毫秒）。"""
    if len(values) < 2:
        return {}
    qs = statistics.quantiles(values, n=100, method="inclusive")
    return {"p50": round(qs[49], 1), "p95": round(qs[94], 1), "p99": round(qs[98], 1)}


async def _snapshot_env(kb) -> dict:
    """抓当次实验的环境变量：库规模 + embeddings 表上现有的索引。

    索引清单直接问 PG 的系统表——「有没有建 HNSW」是本基准最关键的
    实验变量，靠人肉记忆容易记错，让档案自己带上最保险。
    """
    conn = connections.get("default")
    idx_rows = await conn.execute_query_dict(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'embeddings'",
    )
    para_count = await Paragraph.filter(knowledge_base_id=kb.id).count()
    chunk_count = await conn.execute_query_dict(
        "SELECT count(*) AS n FROM embeddings WHERE knowledge_base_id = $1", [kb.id],
    )
    return {
        "kb_name": kb.name,
        "kb_id": str(kb.id),
        "paragraphs": para_count,
        "chunks": chunk_count[0]["n"],
        "embedding_dim": kb.embedding_dim,
        "chunk_config": kb.chunk_config,
        "indexes": [
            r["indexdef"] for r in idx_rows if "hnsw" in r["indexdef"].lower()
        ] or "无向量索引（顺扫）",
    }


async def _explain_search(kb, query_text: str, top_k: int, show_plan: bool) -> float:
    """EXPLAIN ANALYZE 一次检索 SQL，返回服务端纯执行时间（ms，不含网络）。

    show_plan=True 时把完整执行计划打到控制台（看顺扫/索引扫用）。
    """
    vectors = await ModelClient.create_embedding(kb.embedding_model, [query_text.strip()])
    sql = "EXPLAIN (ANALYZE, FORMAT TEXT) " + load_sql("vector_search").format(
        dim=kb.embedding_dim,
    )
    pool = top_k * CANDIDATE_FACTOR
    # 与产品检索同款事务 + 会话参数，EXPLAIN 测的才是产品真实走的计划
    async with in_transaction() as conn:
        await conn.execute_query("SET LOCAL enable_seqscan = off")
        await conn.execute_query(f"SET LOCAL hnsw.ef_search = {max(int(pool), 40)}")
        rows = await conn.execute_query_dict(
            sql, [_to_vector_literal(vectors[0]), kb.id, 0.0, top_k, pool],
        )
    lines = [r["QUERY PLAN"] for r in rows]
    if show_plan:
        print("\n----- 执行计划（样例 1 条）-----")
        print("\n".join(lines))
        print("-----\n")
    # 最后一行形如 "Execution Time: 123.456 ms"
    exec_line = next(l for l in reversed(lines) if l.startswith("Execution Time:"))
    return float(exec_line.split(":")[1].strip().removesuffix(" ms"))


def _save_report(report: dict) -> Path:
    """档案落盘：benchmarks/results/<时间戳>_recall.json，一次测试一份。"""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = results_dir / f"{stamp}_recall.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return path


async def run_eval(args: argparse.Namespace) -> None:
    kb = await _resolve_kb(args.kb)
    queries = _load_queries(Path(args.queries))
    qrels_all = _load_qrels(Path(args.qrels))

    # 段 id → pid 映射（pid 在 import 阶段存进了 Paragraph.title）
    rows = await Paragraph.filter(knowledge_base_id=kb.id).values("id", "title")
    pid_of = {str(r["id"]): r["title"] for r in rows}
    pids_in_db = set(pid_of.values())
    print(f"库内 {len(pids_in_db):,} 段")

    # 只评「标准答案在库里」的 query，防止小规模导入时分数被冤枉拉低
    evaluable = {
        qid: rels for qid, rels in qrels_all.items()
        if qid in queries and any(pid in pids_in_db for pid in rels)
    }
    skipped = len(qrels_all) - len(evaluable)
    if skipped:
        print(f"跳过 {skipped:,} 条答案不在库内的 query")

    qids = sorted(evaluable, key=int)
    if args.limit:
        qids = qids[: args.limit]
    print(f"待评 {len(qids):,} 条 query（top_k={args.top_k}）\n")

    retriever = VectorRetriever()
    run_dict: dict[str, dict[str, float]] = {}
    embed_ms: list[float] = []
    search_ms: list[float] = []
    start_at = time.monotonic()

    for i, qid in enumerate(qids, start=1):
        params = RetrievalParams(query=queries[qid], top_k=args.top_k)
        result = await retriever.retrieve(kb, params)
        run_dict[qid] = {
            pid_of[str(hit.paragraph_id)]: hit.score for hit in result.hits
        }
        embed_ms.append(result.timings["embed_ms"])
        search_ms.append(result.timings["search_ms"])
        if i % 20 == 0 or i == len(qids):
            rate = i / (time.monotonic() - start_at)
            print(f"[eval] {i:,}/{len(qids):,} — {rate:.1f} 条/秒", flush=True)

    # 服务端纯执行时间采样（EXPLAIN ANALYZE，不含网络往返）
    server_ms: list[float] = []
    if args.explain:
        n = min(args.explain, len(qids))
        print(f"\n[explain] 采样 {n} 条 query 的服务端执行时间…")
        for i, qid in enumerate(qids[:n]):
            server_ms.append(
                await _explain_search(kb, queries[qid], args.top_k, show_plan=(i == 0))
            )

    metrics = [f"recall@{args.top_k}", f"mrr@{args.top_k}"]
    scores = evaluate(
        Qrels({qid: evaluable[qid] for qid in qids}), Run(run_dict), metrics,
    )
    report = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "note": args.note,
        "env": await _snapshot_env(kb),
        "params": {"top_k": args.top_k, "queries_evaluated": len(qids)},
        "scores": {name: round(value, 4) for name, value in scores.items()},
        "latency_ms": {
            "search": _percentiles(search_ms),
            "embed": _percentiles(embed_ms),
            "search_server": {
                "sample": len(server_ms), **_percentiles(server_ms),
            } if server_ms else "未采样（--explain N 开启）",
        },
    }
    saved_to = _save_report(report)

    print("\n===== 结果 =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n档案已存：{saved_to}")


def main() -> None:
    parser = argparse.ArgumentParser(description="检索召回 / 延迟评测（基准实验设施）")
    parser.add_argument("--kb", required=True, help="知识库 UUID 或库名")
    parser.add_argument("--queries", required=True, help="dev.query.txt 路径")
    parser.add_argument("--qrels", required=True, help="qrels.dev.tsv 路径")
    parser.add_argument("--top-k", type=int, default=10, help="召回深度（默认 10）")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条 query")
    parser.add_argument("--note", default="", help="本次实验备注（改了什么变量）")
    parser.add_argument(
        "--explain", type=int, default=0,
        help="对前 N 条 query 额外跑 EXPLAIN ANALYZE，采服务端纯执行时间",
    )
    args = parser.parse_args()

    async def _run() -> None:
        await pg_client.connect()
        try:
            await run_eval(args)
        finally:
            await pg_client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
