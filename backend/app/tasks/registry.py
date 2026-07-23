"""异步任务契约表：全项目每个 SAQ 任务的名字与执行策略。

入队侧（service）只引本模块，不碰任务实现——web 进程因此不会被 worker 侧的重依赖
（解析模型、docker SDK 等）拖进来。本模块除 queue 单例外不 import 任何业务代码。

新增任务：这里加一条 TaskSpec → 写任务模块实现 → 在 worker.py 的 functions 登记。
"""

from dataclasses import dataclass
from typing import Any

from saq import Job

from app.tasks.queue import queue


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """一个异步任务的契约：队列里的名字 + 执行策略。

            name 与 Python 符号解耦——日后改函数名，Redis 里已入队的在途任务仍找得到 handler。
            命名用 `<域>.<动作>`，日志与队列指标里一眼看出归属。
        """

    name: str
    timeout: int  # 秒。SAQ 默认只有 10 秒，每个任务必须自报
    retries: int = 3  # 总执行次数，非额外次数（retryable = retries > attempts）
    retry_delay: float = 5.0  # 首次重试前等待秒数
    retry_backoff: bool | float = True  # 指数退避：5s → 10s → 20s

    async def enqueue(self, **kwargs: Any) -> Job | None:
        """入队一个任务实例。

            kwargs 是任务函数的参数，经 Redis 做 JSON 序列化，只能传 JSON 原生类型
            （UUID / datetime 等在入队侧转 str，任务函数里还原）。
        """
        return await queue.enqueue(
            self.name,
            timeout=self.timeout,
            retries=self.retries,
            retry_delay=self.retry_delay,
            retry_backoff=self.retry_backoff,
            **kwargs,
        )

# === 知识库 ===

# 解析 → 切段 → 切块 → 向量化整条管线。大文档分批 embedding 慢，给足 30 分钟
PROCESS_DOCUMENT = TaskSpec(name="knowledge.process_document", timeout=1800)