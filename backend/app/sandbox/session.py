"""会话表 —— 「session_id → 容器句柄」的进程内登记簿。

只在内存里，不落库。两个理由：会话活不过一次回复，比任何一条数据都短命；
而且 docker 的 Container 句柄本来就没法序列化存起来。
代价是 **sandboxd 一重启，所有会话失效** —— 所以启动时必须把带标记的容器
全清一遍（`reap_expired(0)`），否则它们就成了没人认领的孤儿。
"""

import threading

from docker.models.containers import Container
from uuid_utils import uuid4

from app.sandbox import container as docker_ops


class SessionRegistry:
    """线程安全的会话登记簿。

    为什么要锁：端点是同步函数，FastAPI 会把它们丢进线程池执行 —— 多个请求是
    **真并行**，字典的读写不加锁会撞。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Container] = {}
        self._lock = threading.Lock()

    def open(self, env: dict[str, str]) -> str:
        """起一个容器，登记后返回 session_id。"""
        session_id = uuid4().hex
        # 建容器要几秒，**故意放在锁外面** —— 持锁做 I/O 会把并发的其他请求全堵住
        instance = docker_ops.create_container(session_id, env)
        with self._lock:
            self._sessions[session_id] = instance
        return session_id

    def get(self, session_id: str) -> Container:
        """取容器句柄。

        Raises:
            KeyError: 会话不存在（已销毁 / 被反收割清掉 / sandboxd 重启过）
        """
        with self._lock:
            instance = self._sessions.get(session_id)
        if instance is None:
            raise KeyError(session_id)
        return instance

    def close(self, session_id: str) -> None:
        """销毁容器并注销。重复调用不报错 —— 正常结束和反收割可能都会走到这儿。"""
        with self._lock:
            instance = self._sessions.pop(session_id, None)
        if instance is not None:
            docker_ops.destroy(instance)

registry = SessionRegistry()