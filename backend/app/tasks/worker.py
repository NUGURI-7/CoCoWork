"""SAQ worker 配置。

worker 是独立进程,靠 `uv run worker` 启动(见 app/cli.py);SAQ 读这里的
`settings` 字典构造 Worker(内部 Worker(**settings))。

- worker 没有 FastAPI 的 lifespan,凡是 web 侧在 lifespan 里做的初始化,这里都得
  自己重做一遍:数据库连接(Tortoise 连接绑在 worker 自己的进程 / 事件循环上)、
  日志(见 cli.worker)、jieba 词典、checkpointer 连接池。新增此类初始化时记得
  两边都要过一遍
- functions = 任务函数清单：worker 只执行登记在这里的函数。新增任务要在这里
  登记并重启 worker，否则 job 入队后没人认领。将来拆多 worker（重任务独占进程）
  就按这份清单分组
"""
import jieba
from tortoise import Tortoise

from app.core.redis import redis_client
from app.db.checkpointer import init_checkpointer, shutdown_checkpointer
from app.db.postgresql import TORTOISE_CONFIG
from app.tasks.checkpoint_cleanup_task import cleanup_checkpoints_task
from app.tasks.document_task import process_document_task
from app.tasks.memory_digest_task import digest_memory_task
from app.tasks.registry import CLEANUP_CHECKPOINTS, DIGEST_MEMORY, PROCESS_DOCUMENT
from app.tasks.queue import queue


async def startup(ctx: dict) -> None:
    """worker 进程启动时跑一次:开数据库连接 + Redis + checkpointer 池 + 预热分词词典。"""
    await Tortoise.init(config=TORTOISE_CONFIG)
    await redis_client.connect()  # 云端解析的 token 缓存要用
    # checkpointer 归 worker 用,不是给它跑图 —— 存档清理任务要经 saver 删存档。
    # 里面的建表是幂等的:web 侧早把迁移跑完了,这边只剩一次版本号查询
    await init_checkpointer()
    jieba.initialize()


async def shutdown(ctx: dict) -> None:
    """worker 进程退出时跑一次:关数据库连接 + Redis + checkpointer 池。"""
    await Tortoise.close_connections()
    await redis_client.close()
    await shutdown_checkpointer()


settings = {
    "queue": queue,
    "functions": [                                      # 一行一个任务
        (PROCESS_DOCUMENT.name, process_document_task),
        (DIGEST_MEMORY.name, digest_memory_task),
    ],
    # 定时任务。函数不用再进上面的 functions —— SAQ 会自己把 cron 的函数并进去
    "cron_jobs": [
        CLEANUP_CHECKPOINTS.to_cron_job(cleanup_checkpoints_task),
    ],
    "concurrency": 3,  # 同时嚼几个任务；重 IO 任务防打爆上游 API，先保守设 3
    "startup": startup,
    "shutdown": shutdown,
}
