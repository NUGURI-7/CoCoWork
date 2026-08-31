"""SAQ 任务队列单例。

web 进程(入队)和 worker 进程(取任务执行)都 import 这同一个 queue,
两侧靠同一个 Redis + 同一个队列名指向同一个「信箱」。

- 底层复用项目现有 Redis(settings.redis_url)
- Queue 对象 import 即建、很轻;真正的「连接」:web 侧由 lifespan
  connect()/disconnect() 管理,worker 侧 SAQ 自己管理
"""
from redis import asyncio as aioredis
from saq.queue.redis import RedisQueue

from app.core.config import settings
from app.core.redis import REDIS_HEALTH_CHECK_INTERVAL

# name 决定 Redis 里的 key 前缀(saq:cocowork:*);和 DaisyWind 共用一个 Redis
# 时,靠这个前缀隔离,不会和 app 其它 Redis 用途撞 key
#
# **不用 Queue.from_url**:它的 **kwargs 是给 RedisQueue 自己的(dump/load/
# max_concurrent_ops 那些),传不到底下的 redis 客户端 —— 保活参数写在那儿会被
# 静默吞掉。所以这里自己建 redis 客户端再交给 RedisQueue。
# 保活的理由见 app/core/redis.py 顶部:worker 空队列时一闲就是几分钟,
# 比 web 请求更容易撞上「连接被中间设备静默掐断」。
queue = RedisQueue(
    aioredis.from_url(
        settings.redis_url,
        health_check_interval=REDIS_HEALTH_CHECK_INTERVAL,
        socket_keepalive=True,
    ),
    name="cocowork",
)
