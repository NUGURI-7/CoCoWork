"""进程入口:uv run dev(web) / uv run worker(任务队列)。

main.py 只负责「定义 FastAPI app」;进程怎么起、起哪个,归这里。
两个身份分开,app 定义不掺启动逻辑。

main.py 底部的 `__main__` 转调这里的 dev(),所以 IDE 直接跑 main.py
和终端 `uv run dev` 走的是同一个函数,不会出现两处配置漂移。
"""
from app.core.config import settings


def dev() -> None:
    """启动 FastAPI(开发)。"""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        access_log=False,
    )


def worker() -> None:
    """启动 SAQ worker(取任务执行)。

    worker 是独立进程、不经过 main.py,所以日志得自己配一次——否则 SAQ 的
    输出全掉进黑洞,进程活着却一声不吭,运维上分不清它在干活还是死了。

    start() 是阻塞的:进程就此常驻,不停从队列取任务跑,直到被杀。
    """
    from saq.worker import start

    from app.core.logging import setup_logging

    setup_logging()
    start("app.tasks.worker.settings")
