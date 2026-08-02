"""LangGraph checkpointer —— 图执行状态的持久化。

与业务库的分工：**两回事，各存各的**。

- `Message` 表存「聊了什么」：给前端渲染、按应答者视角化、长期保留
- checkpoint 表存「跑到哪儿了」：只有 LangGraph 引擎会读，一轮跑完即废

所以它不走 Tortoise、也不进 `migrations/` —— 那几张表由 LangGraph 用
`setup()` 自建自管（幂等），属框架私产，业务侧不碰、不查、不 JOIN。
在 `migrations/` 里找不到它们不是遗漏，是本就不该在那儿。

连接池独立且比业务池小得多，理由见 `settings.PG_CHECKPOINT_POOL_*` 的注释。
"""

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)


def _conninfo() -> str:
    """psycopg 连接串 —— 用官方的 make_conninfo 拼，**不手写 URL**。

    手写 `postgresql://user:pass@host/db` 会被密码里的 @ / : / # 等字符切坏
    （本项目的密码就含 @，手写版把 host 解析成了 `Ly@118.25.77.231`）。
    make_conninfo 产出的是 keyword/value 格式并自行处理转义，这类问题不复存在。

    与 Tortoise 共用同一批 PG_* 配置项：换数据库地址时两边一起变，不会漏一处。
    """
    return make_conninfo(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        dbname=settings.PG_DATABASE,
    )

# 进程内单例：整个进程只造一次，所有装配点共用。
# 连接池是重量级资源（建 TCP + 认证），且每造一个就占掉若干条连接 ——
# 若改成每次装配图时新建，并发一上来就会撞满 Postgres 的连接数上限。
_saver: AsyncPostgresSaver | None = None
_pool: AsyncConnectionPool | None = None

# 三个参数都不是可选项，少一个就会在特定时机炸：
# - autocommit：checkpoint 写入是一条条独立短事务，不要外层事务包着攒到最后
# - prepare_threshold=0：关掉预备语句。池会复用连接，预备语句名在连接之间
#   撞车会抛 InvalidSqlStatementName（langgraph#2755）—— 用池就必须配
# - row_factory=dict_row：让每行以 dict 返回。saver 内部按列名取值
#   （row["thread_id"] 这种写法），默认的元组行会直接 TypeError
_CONNECTION_KWARGS = {
    "autocommit": True,
    "prepare_threshold": 0,
    "row_factory": dict_row,
}


async def init_checkpointer() -> None:
    """开池 + 建表，启动期调用一次。

    三步是一条链，缺一不可：池是 saver 的零件（saver 自己不管连接，
    要外部把连接交给它），建表则要通过 saver 发出去。

    失败直接抛、应用起不来：连不上数据库是启动期就该暴露的问题，
    没有理由拖到第一次对话跑到一半才发现。
    """
    global _saver, _pool
    if _saver is not None:  # 幂等：重复调用（测试夹具等）直接返回
        return

    pool = AsyncConnectionPool(
        conninfo=_conninfo(),
        min_size=settings.PG_CHECKPOINT_POOL_MIN_SIZE,
        max_size=settings.PG_CHECKPOINT_POOL_MAX_SIZE,
        kwargs=_CONNECTION_KWARGS,
        # 取连接时先验活。默认不验（check=None），池会把已被服务端掐掉的连接
        # 直接交出去 —— 隔一阵不聊天再发一句就报 server closed the connection
        # unexpectedly（远程库和中间的防火墙都会掐空闲连接）。
        # 验活失败时池自己丢弃重连，调用方无感
        check=AsyncConnectionPool.check_connection,
        # 构造函数里不做 IO：否则这行看着只是「造个对象」，实际却偷偷连了网络，
        # 连不上时报错从一句赋值里抛出来。显式 open 才能让失败点一眼可辨
        open=False,
    )
    # wait=True：等连接真建立好再往下走。否则启动日志一片绿，
    # 要等第一次对话跑到写 checkpoint 时才发现连不上 —— 那时 SSE 已经开着了
    await pool.open(wait=True)

    saver = AsyncPostgresSaver(pool)
    await saver.setup()  # 幂等建表 + 跑框架自己的内部迁移

    _pool, _saver = pool, saver
    logger.info(
        "✅ LangGraph checkpointer 就绪（独立池 %d~%d 条连接）",
        settings.PG_CHECKPOINT_POOL_MIN_SIZE,
        settings.PG_CHECKPOINT_POOL_MAX_SIZE,
    )


def get_checkpointer() -> AsyncPostgresSaver:
    """取单例，供装配期挂到图上 —— 是「从架子上取」，不是「造」。

    未初始化即抛：装配期拿不到它意味着这次对话不可暂停也不可恢复，
    与其让它悄悄退化成一次性对话，不如当场失败。
    """
    if _saver is None:
        raise RuntimeError(
            "checkpointer 未初始化 —— 检查 lifespan 是否调用了 init_checkpointer()"
        )
    return _saver


async def shutdown_checkpointer() -> None:
    """关池，与 init 对称，挂在 lifespan 的 finally 里。"""
    global _saver, _pool
    if _pool is not None:
        await _pool.close()
        logger.info("👋 LangGraph checkpointer 连接池已关闭")
    _saver, _pool = None, None
