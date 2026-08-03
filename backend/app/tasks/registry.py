"""异步任务契约表：全项目每个 SAQ 任务的名字与执行策略。

入队侧（service）只引本模块，不碰任务实现——web 进程因此不会被 worker 侧的重依赖
（解析模型、docker SDK 等）拖进来。本模块除 queue 单例外不 import 任何业务代码。

新增任务：这里加一条 TaskSpec → 写任务模块实现 → 在 worker.py 的 functions 登记。
定时任务用 CronSpec，最后一步改为在 worker.py 的 cron_jobs 里 to_cron_job 绑函数。
"""

from dataclasses import dataclass
from typing import Any

from saq import CronJob, Job
from saq.types import Function

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

    async def enqueue(self, *, key: str | None = None, **kwargs: Any) -> Job | None:
        """入队一个任务实例。

            kwargs 是任务函数的参数，经 Redis 做 JSON 序列化，只能传 JSON 原生类型
            （UUID / datetime 等在入队侧转 str，任务函数里还原）。

            key 是**去重键**：同一个 key 的任务只要还没跑完（排队中或正在跑），
            再入队直接返回 None —— 注意是**丢弃，不是排在后面等**。适合「这次丢了
            下次还会来、且下次读的是同一批数据」的周期性任务；不适合每一次都必须
            执行到的任务。不传则每次都入队。

            写成显式形参而不是混在 kwargs 里：SAQ 会把撞上 Job 字段名的 kwarg
            悄悄当成 Job 属性（不是任务参数），一个叫 key 的业务参数会就这么消失。
        """
        return await queue.enqueue(
            self.name,
            timeout=self.timeout,
            retries=self.retries,
            retry_delay=self.retry_delay,
            retry_backoff=self.retry_backoff,
            **({"key": key} if key else {}),
            **kwargs,
        )


@dataclass(frozen=True, slots=True)
class CronSpec:
    """一个定时任务的契约：多久跑一次 + 执行策略。

        与 TaskSpec 的三点不同：

        - **没有 name**。SAQ 的 CronJob 只收裸函数，队列里的名字由它自己取自
          `函数.__qualname__` —— TaskSpec 那条「名字与 Python 符号解耦」在这儿
          落不了地。认了：那条防的是「入队后躺着等人取」的任务改名丢 handler，
          cron 没这个风险，改名重启后下个周期照常来。
        - **不自己入队**。谁来定时入队是 worker 的事（它按 cron 算下一次的时刻），
          这里只描述「多久一次、跑多久算超时」。
        - **函数不在这儿绑**。本模块不 import 任何业务代码（见模块 docstring），
          绑定发生在 worker.py 的 cron_jobs。
        """

    cron: str  # 五段 croniter 表达式，**按 UTC 算**（Worker 的 cron_tz 默认 UTC）
    timeout: int  # 秒。同 TaskSpec：不显式给会掉回 SAQ 的 10 秒默认
    retries: int = 0  # 定时任务默认不重试：这次没跑成，下个周期自然还会来

    def to_cron_job(self, function: Function) -> CronJob:
        """绑上函数，交给 worker 的 cron_jobs。"""
        return CronJob(
            function=function,
            cron=self.cron,
            timeout=self.timeout,
            retries=self.retries,
        )


# === 知识库 ===

# 解析 → 切段 → 切块 → 向量化整条管线。大文档分批 embedding 慢，给足 30 分钟
PROCESS_DOCUMENT = TaskSpec(name="knowledge.process_document", timeout=1800)


# === 记忆 ===

# 每 N 轮从最近的用户发言里沉淀一次常驻记忆。就一次模型调用，2 分钟够宽。
# retries=0 是刻意的：这次没跑成，下次到点自然还会来，而且读的还是同一批消息，
# 重试只会多烧一次模型调用。跟文档处理相反 —— 那个丢了用户永远卡在「处理中」
DIGEST_MEMORY = TaskSpec(name="memory.digest", timeout=120, retries=0)


# === 图存档（LangGraph checkpoint）===

# 每天清一次。UTC 18:00 = 北京时间凌晨 2 点，避开白天在用的时候
# （cron 按 UTC 算，见 CronSpec.cron 的注释）。
# timeout 给 10 分钟：一批最多 5000 个 thread、每个一次数据库往返，
# 远端库按 50ms 算也就 4 分钟出头，留一倍余量
CLEANUP_CHECKPOINTS = CronSpec(cron="0 18 * * *", timeout=600)
