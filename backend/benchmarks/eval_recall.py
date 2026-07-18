"""检索召回 / 延迟评测脚本（检索基准配套，不进产品）。

拿 Multi-CPR 的 dev query + qrels 考产品检索链路（产品 Retriever 原样复用，
测的就是产品真实路径）：每条 query 走一次检索 → 命中段查回 pid → 与 qrels
对分。指标交给 ranx（recall@k / MRR@k），延迟取 retriever 自带的
timings 埋点分位数。

用法（在 backend/ 目录下）::

    uv run python -m benchmarks.eval_recall --kb 医疗检索基准 \\
        --queries ../data/medical/dev.query.txt \\
        --qrels ../data/medical/qrels.dev.tsv

- ``--mode``：检索模式 vector（默认）/ keyword，与产品 RetrievalMode 同名对齐
- ``--workers``：并发数（默认 1 = 顺序）。质量分数不受并发影响；客户端延迟
  分位数只在顺序跑时采集（并发互相挤占、耗时测的是排队不是查询），并发跑时
  延迟以 ``--explain`` 的服务端采样为准（它始终独立顺序执行、不受污染）
- ``--limit``：只跑前 N 条 query（快速冒烟）
- ``--top-k``：召回深度（默认 10，即 recall@10 / mrr@10）
- 标准答案不在库里的 query 自动跳过并报数（小规模导入时防止分数被冤枉拉低）
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
from app.services.knowledge.retrieval.base import RetrievalMode, RetrievalParams
from app.services.knowledge.retrieval.keyword import (
    KeywordRetriever,
    _to_tsquery_literal,
)
from app.services.knowledge.retrieval.sql import load_sql
from app.services.knowledge.retrieval.vector import (
    CANDIDATE_FACTOR,
    VectorRetriever,
    _to_vector_literal,
)
from app.services.knowledge.stopwords import STOPWORDS
from app.services.knowledge.tokenization import tokenize_query
from app.services.model import ModelClient
from benchmarks.import_corpus import _resolve_kb

# BGE v1/v1.5 官方检索指令（query 侧专用，语料侧不加）；
# 官方称 v1.5 不加也只轻微下降——本脚本 --query-prefix 就是来实测这个「轻微」的
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


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
    """抓当次实验的环境变量：库规模 + 两张表上现有的检索索引 + 分词口径。

    索引清单直接问 PG 的系统表——「有没有建 HNSW / GIN」是本基准最关键的
    实验变量，靠人肉记忆容易记错，让档案自己带上最保险。停用词表规模同理：
    keyword 模式的分数随词表口径漂移，档案必须记下当时的口径。
    """
    conn = connections.get("default")
    idx_rows = await conn.execute_query_dict(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE tablename IN ('embeddings', 'paragraphs')",
    )
    para_count = await Paragraph.filter(knowledge_base_id=kb.id).count()
    chunk_count = await conn.execute_query_dict(
        "SELECT count(*) AS n FROM embeddings WHERE knowledge_base_id = $1", [kb.id],
    )
    retrieval_indexes = [
        r["indexdef"] for r in idx_rows
        if "hnsw" in r["indexdef"].lower() or "gin" in r["indexdef"].lower()
    ]
    return {
        "kb_name": kb.name,
        "kb_id": str(kb.id),
        "paragraphs": para_count,
        "chunks": chunk_count[0]["n"],
        "embedding_dim": kb.embedding_dim,
        "chunk_config": kb.chunk_config,
        "indexes": retrieval_indexes or "无检索索引（顺扫）",
        "tokenizer": {"stopwords": len(STOPWORDS)},
    }


def _extract_exec_ms(rows: list[dict], show_plan: bool) -> float:
    """EXPLAIN ANALYZE 结果行 → 服务端纯执行时间（ms）；show_plan 时打完整计划。"""
    lines = [r["QUERY PLAN"] for r in rows]
    if show_plan:
        print("\n----- 执行计划（样例 1 条）-----")
        print("\n".join(lines))
        print("-----\n")
    # 最后一行形如 "Execution Time: 123.456 ms"
    exec_line = next(l for l in reversed(lines) if l.startswith("Execution Time:"))
    return float(exec_line.split(":")[1].strip().removesuffix(" ms"))


async def _explain_search(kb, query_text: str, top_k: int, show_plan: bool) -> float:
    """EXPLAIN ANALYZE 一次向量检索 SQL（与产品同事务同会话参数）。"""
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
    return _extract_exec_ms(rows, show_plan)


async def _explain_search_keyword(kb, query_text: str, top_k: int, show_plan: bool) -> float:
    """EXPLAIN ANALYZE 一次全文检索 SQL（产品 keyword 路径无事务无会话参数，同款）。"""
    tokens = tokenize_query(query_text)
    if not tokens:
        return 0.0
    sql = "EXPLAIN (ANALYZE, FORMAT TEXT) " + load_sql("keyword_search")
    rows = await connections.get("default").execute_query_dict(
        sql, [kb.id, _to_tsquery_literal(tokens), 0.0, top_k],
    )
    return _extract_exec_ms(rows, show_plan)


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

    mode = RetrievalMode(args.mode)
    retriever = {
        RetrievalMode.VECTOR: VectorRetriever(),
        RetrievalMode.KEYWORD: KeywordRetriever(),
    }[mode]
    run_dict: dict[str, dict[str, float]] = {}
    embed_ms: list[float] = []
    search_ms: list[float] = []
    start_at = time.monotonic()
    done = 0
    failed: dict[str, str] = {}
    consec_fail = 0

    # 信号量限流 + 全量 gather（流水式：谁完成谁让位，并发位永远坐满；
    # 分批 gather 会让每批等最慢一条，慢尾巴拖空并发位）
    sem = asyncio.Semaphore(args.workers)

    async def _eval_one(qid: str) -> None:
        nonlocal done, consec_fail
        async with sem:
            params = RetrievalParams(
                query=args.query_prefix + queries[qid], top_k=args.top_k, mode=mode,
            )
            # 单条超时兜底：远端连接半死（TCP 断了没通知）会让 await 永远等下去，
            # 与其无声卡死不如记败继续；连续多条失败 = 连接大概率已死，熔断止损
            try:
                result = await asyncio.wait_for(
                    retriever.retrieve(kb, params), timeout=args.timeout,
                )
            except Exception as e:  # noqa: BLE001 —— 实验设施，记案底不挑错型
                failed[qid] = f"{type(e).__name__}: {e}"
                consec_fail += 1
                print(f"[warn] qid={qid} 检索失败：{failed[qid]}", flush=True)
                if consec_fail >= 5:
                    raise SystemExit(
                        "连续 5 条失败——数据库连接大概率已死，中止本次评测"
                    ) from e
                done += 1
                return
        consec_fail = 0
        run_dict[qid] = {
            pid_of[str(hit.paragraph_id)]: hit.score for hit in result.hits
        }
        # timings 形态随 mode 不同（keyword 无 embed），有哪段收哪段
        if "embed_ms" in result.timings:
            embed_ms.append(result.timings["embed_ms"])
        search_ms.append(result.timings["search_ms"])
        done += 1
        if done % 20 == 0 or done == len(qids):
            rate = done / (time.monotonic() - start_at)
            print(f"[eval] {done:,}/{len(qids):,} — {rate:.1f} 条/秒", flush=True)

    await asyncio.gather(*(_eval_one(qid) for qid in qids))
    if failed:
        print(f"\n[warn] {len(failed)} 条 query 检索失败，已从评分中剔除：{sorted(failed, key=int)}")

    # 服务端纯执行时间采样（EXPLAIN ANALYZE，不含网络往返）
    server_ms: list[float] = []
    explain_fn = (
        _explain_search if mode is RetrievalMode.VECTOR else _explain_search_keyword
    )
    if args.explain:
        n = min(args.explain, len(qids))
        print(f"\n[explain] 采样 {n} 条 query 的服务端执行时间…")
        for i, qid in enumerate(qids[:n]):
            server_ms.append(
                await explain_fn(kb, queries[qid], args.top_k, show_plan=(i == 0))
            )

    metrics = [f"recall@{args.top_k}", f"mrr@{args.top_k}"]
    scored_qids = [qid for qid in qids if qid in run_dict]  # 失败的不计分也不算分母
    scores = evaluate(
        Qrels({qid: evaluable[qid] for qid in scored_qids}), Run(run_dict), metrics,
    )
    # 客户端延迟只在顺序跑时可信：并发下每条耗时混入排队时间，测的是拥挤不是查询
    if args.workers == 1:
        client_latency = {
            "search": _percentiles(search_ms),
            "embed": _percentiles(embed_ms) or "无（keyword 模式不调 embedding）",
        }
    else:
        client_latency = {
            "search": f"未采（workers={args.workers} 并发跑，以 search_server 为准）",
            "embed": f"未采（workers={args.workers} 并发跑）",
        }
    report = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "note": args.note,
        "env": await _snapshot_env(kb),
        "params": {
            "mode": mode.value,
            "top_k": args.top_k,
            "workers": args.workers,
            "queries_evaluated": len(scored_qids),
            "queries_failed": len(failed),
            "query_prefix": args.query_prefix,
        },
        "scores": {name: round(value, 4) for name, value in scores.items()},
        "latency_ms": {
            **client_latency,
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
    parser.add_argument(
        "--mode", choices=[m.value for m in RetrievalMode], default="vector",
        help="检索模式（默认 vector）",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="并发数（默认 1 = 顺序跑并采集客户端延迟；>1 只出质量分，提防 API 限流别开太大）",
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0,
        help="单条 query 检索超时秒数（防远端连接半死无声卡死，默认 30）",
    )
    parser.add_argument("--top-k", type=int, default=10, help="召回深度（默认 10）")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条 query")
    parser.add_argument("--note", default="", help="本次实验备注（改了什么变量）")
    parser.add_argument(
        "--explain", type=int, default=0,
        help="对前 N 条 query 额外跑 EXPLAIN ANALYZE，采服务端纯执行时间",
    )
    parser.add_argument(
        "--query-prefix", nargs="?", const=BGE_QUERY_INSTRUCTION, default="",
        help="query 侧检索指令前缀；裸给此参数 = BGE 官方指令，也可自定义字符串",
    )
    args = parser.parse_args()
    if args.mode == RetrievalMode.KEYWORD.value and args.query_prefix:
        raise SystemExit(
            "--query-prefix 是 vector 模式的 BGE 指令实验参数；"
            "keyword 模式下前缀会被当正文分词进查询，禁止混用"
        )

    async def _run() -> None:
        await pg_client.connect()
        try:
            await run_eval(args)
        finally:
            await pg_client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
