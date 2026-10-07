"""按库建的 HNSW 部分索引：索引定义与检索 SQL 共用的写法收口在这里。

`Embedding.embedding` 列不锁维度（各库可选不同模型），HNSW 又必须知道维度，
所以只能每库一条部分索引：`(embedding::vector(dim))` + `WHERE knowledge_base_id = 库`。
PG 只在查询表达式与索引表达式一致时才用索引，不一致不报错、静默顺扫——
因此转换类型只在 `vector_type()` 定义一次，检索 SQL 与建索引语句都从这里取。
"""
import asyncio
import logging
from uuid import UUID

from tortoise import connections

logger = logging.getLogger(__name__)

# 同库另一篇文档正在建索引时，隔多久再试一次拿锁
_LOCK_RETRY_SECONDS = 0.5

# pgvector 的 HNSW 对 vector 类型的维度上限：一条索引记录须放进一个 8KB 数据页，
# float32 每维 4 字节。超过的库不建索引、检索走顺扫（与 Dify / MaxKB 的 pgvector 实现一致）。
HNSW_MAX_DIM = 2000


def vector_type(dim: int) -> str:
    """检索与索引共用的转换类型，如 ``vector(1024)``。"""
    return f"vector({dim})"


def supports_hnsw(dim: int) -> bool:
    return dim <= HNSW_MAX_DIM


def hnsw_index_name(kb_id: UUID) -> str:
    """``embeddings_hnsw_<kb_id 十六进制>``，48 字符，在 PG 标识符 63 字符上限内。"""
    return f"embeddings_hnsw_{kb_id.hex}"


def create_hnsw_index_sql(kb_id: UUID, dim: int) -> str:
    """建索引 DDL。CONCURRENTLY 不阻塞其他库写入 embeddings，代价是不能在事务内执行。

    DDL 不支持参数绑定，kb_id 只能拼进语句；入参限定 UUID 类型，文本形式只含十六进制与横线。
    """
    if not supports_hnsw(dim):
        raise ValueError(f"维度 {dim} 超过 HNSW 上限 {HNSW_MAX_DIM}，不能建索引")
    return (
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {hnsw_index_name(kb_id)} "
        f"ON embeddings USING hnsw ((embedding::{vector_type(dim)}) vector_cosine_ops) "
        f"WHERE knowledge_base_id = '{kb_id}'"
    )


async def ensure_hnsw_index(kb_id: UUID, dim: int) -> None:
    """确保库的 HNSW 索引存在且可用；写向量前调用，已就绪时只多一次系统表查询。

    同库多篇文档会被 worker 并发处理，用会话级 advisory lock 让「检查 + 建索引」同库串行，
    免得后来者把前者正在建、尚未生效的索引当成失效索引删掉。
    锁、检查、建索引须在同一条连接上：advisory lock 归属连接，CONCURRENTLY 要求不在事务内。
    拿锁用 try 轮询而非阻塞等待：阻塞中的语句持有快照，CONCURRENTLY 会反过来等它，形成互等。
    """
    if not supports_hnsw(dim):
        logger.warning(
            "知识库 %s 向量维度 %d 超过 HNSW 上限 %d，不建索引，向量检索走顺扫",
            kb_id, dim, HNSW_MAX_DIM,
        )
        return

    name = hnsw_index_name(kb_id)
    async with connections.get("default").acquire_connection() as conn:
        while not await conn.fetchval("SELECT pg_try_advisory_lock(hashtext($1))", name):
            await asyncio.sleep(_LOCK_RETRY_SECONDS)
        try:
            valid = await conn.fetchval(
                "SELECT i.indisvalid FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid WHERE c.relname = $1",
                name,
            )
            if valid:
                return
            if valid is False:
                # CONCURRENTLY 中途失败会留下失效索引；不删掉，IF NOT EXISTS 会永远跳过它
                await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            await conn.execute(create_hnsw_index_sql(kb_id, dim))
            logger.info("知识库 %s 已建 HNSW 索引 %s", kb_id, name)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(hashtext($1))", name)


async def drop_hnsw_index(kb_id: UUID) -> None:
    """删库后清掉该库的 HNSW 索引。

    CONCURRENTLY 不阻塞其他库读写 embeddings；IF EXISTS 兼容从没写过向量、没建过索引的库。
    """
    await connections.get("default").execute_script(
        f"DROP INDEX CONCURRENTLY IF EXISTS {hnsw_index_name(kb_id)}"
    )
