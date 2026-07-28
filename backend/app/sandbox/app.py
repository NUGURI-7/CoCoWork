"""sandboxd 的进程装配 —— app 对象 + 生命周期。

为什么是独立进程而不是 web 的一个路由（§3）：挂 docker.sock ≈ 交出整台机器，
而 web 是对外开着 API 的那个进程，不该拿这个权力。
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.sandbox import container as docker_ops
from app.sandbox.api import router


logger = logging.getLogger(__name__)

# 巡检间隔。它决定「一个超时的容器最多还能多活多久」= TTL + 这个间隔
_REAP_INTERVAL = 60

async def _reaper_loop() -> None:
    """定时清理活过 TTL 的容器，直到进程退出。

    单开一个后台任务，而不是「顺手在某个请求里清」：**没有请求进来的时候，
    漏网的容器才最需要有人管**。
    """
    while True:
        await asyncio.sleep(_REAP_INTERVAL)
        try:
            await run_in_threadpool(
                docker_ops.reap_expired, settings.SANDBOX_SESSION_TTL
            )
        except Exception:
            # 失败绝不能让循环退出 —— 循环一停，唯一的兜底就没了，而且没人会发现
            logger.exception("反收割巡检失败，下一轮继续")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.SANDBOX_TOKEN:
        raise RuntimeError("SANDBOX_TOKEN 未配置：sandboxd 握着 docker.sock，不许裸奔")

    docker_ops.ensure_network()
    # 启动先全清：会话句柄只活在上一个进程的内存里，重启后所有带标记的容器
    # 都成了没人认领的孤儿，留着纯占资源
    orphans = docker_ops.reap_expired(0)
    if orphans:
        logger.warning("启动时清理了 %d 个上次遗留的沙箱容器", orphans)

    reaper = asyncio.create_task(_reaper_loop())
    logger.info("🧰 sandboxd 就绪 %s:%s", settings.SANDBOXD_HOST, settings.SANDBOXD_PORT)
    try:
        yield
    finally:
        reaper.cancel()

app = FastAPI(title="CoCoWork sandboxd", lifespan=lifespan)
app.include_router(router)



