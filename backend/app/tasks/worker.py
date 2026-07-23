"""SAQ worker 配置。

worker 是独立进程,靠 `uv run worker` 启动(见 app/cli.py);SAQ 读这里的
`settings` 字典构造 Worker(内部 Worker(**settings))。

- worker 没有 FastAPI 的 lifespan,数据库要在 startup 里自己初始化、
  shutdown 里关掉(Tortoise 连接绑在 worker 自己的进程 / 事件循环上)
- functions = 任务函数清单：worker 只执行登记在这里的函数。新增任务要在这里
  登记并重启 worker，否则 job 入队后没人认领。将来拆多 worker（重任务独占进程）
  就按这份清单分组
"""
from tortoise import Tortoise

from app.db.postgresql import TORTOISE_CONFIG
from app.tasks.document_task import process_document_task
from app.tasks.registry import PROCESS_DOCUMENT
from app.tasks.queue import queue


async def startup(ctx: dict) -> None:
    """worker 进程启动时跑一次:开数据库连接。"""
    await Tortoise.init(config=TORTOISE_CONFIG)


async def shutdown(ctx: dict) -> None:
    """worker 进程退出时跑一次:关数据库连接。"""
    await Tortoise.close_connections()


settings = {
    "queue": queue,
    "functions": [(PROCESS_DOCUMENT.name, process_document_task)],  # 一行一个任务
    "concurrency": 3,  # 同时嚼几个任务；重 IO 任务防打爆上游 API，先保守设 3
    "startup": startup,
    "shutdown": shutdown,
}
