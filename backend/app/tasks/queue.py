"""SAQ 任务队列单例。

web 进程(入队)和 worker 进程(取任务执行)都 import 这同一个 queue,
两侧靠同一个 Redis + 同一个队列名指向同一个「信箱」。

- 底层复用项目现有 Redis(settings.redis_url)
- Queue 对象 import 即建、很轻;真正的「连接」:web 侧由 lifespan
  connect()/disconnect() 管理,worker 侧 SAQ 自己管理
"""
from saq import Queue

from app.core.config import settings

# name 决定 Redis 里的 key 前缀(saq:cocowork:*);和 DaisyWind 共用一个 Redis
# 时,靠这个前缀隔离,不会和 app 其它 Redis 用途撞 key
queue = Queue.from_url(settings.redis_url, name="cocowork")
