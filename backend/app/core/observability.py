"""Langfuse 可观测接缝 —— v4 SDK 的 LangChain 集成 + trace 归因。

v4 凭证契约(官方文档 + 实测核实):get_client() / CallbackHandler() 只认 os.environ,
构造参数绑不上 handler。故由 init_langfuse() 在启动时把 settings 的 key 桥接进 os.environ。
降级:没配 key → 全链路 no-op,零报错。
"""
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings


@dataclass(slots=True)
class TraceContext:
    """一次对话的 trace 归因 —— 透传给 Langfuse 当聚合/过滤维度。"""

    user_id: str | None = None
    session_id: str | None = None  # = conversation_id,Sessions 视图按会话聚合
    name: str | None = None  # trace 名(Tracing 列表 Name 列):workspace_chat / playground
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_config_metadata(self) -> dict[str, Any]:
        """拼 RunnableConfig.metadata。langfuse_* 是 v4 handler 约定的归因键。

        trace 名走 langfuse_trace_name —— run_name 只设 span 名、设不了 trace 名
        (实测列表 Name 列空白即此故),v4 CallbackHandler 认 langfuse_trace_name。
        """
        meta: dict[str, Any] = dict(self.metadata)
        if self.user_id:
            meta["langfuse_user_id"] = self.user_id
        if self.session_id:
            meta["langfuse_session_id"] = self.session_id
        if self.name:
            meta["langfuse_trace_name"] = self.name
        if self.tags:
            meta["langfuse_tags"] = self.tags
        return meta


_handler = None


def _langfuse_configured() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def init_langfuse() -> bool:
    """启动时桥接凭证 + 建 handler —— v4 只认 os.environ,且 handler 必须在 env 就绪后建。

    lifespan 启动处调用。setdefault:真实环境变量优先,.env 兜底。
    返回是否启用(供启动日志);未配 key → 跳过,应用照常。
    """
    global _handler
    if not _langfuse_configured():
        return False

    import os
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
    os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)

    from langfuse.langchain import CallbackHandler
    _handler = CallbackHandler()  # env 已就绪,handler 带凭证
    return True


def get_langfuse_handler():
    """Langfuse CallbackHandler;init_langfuse() 没跑或没配 key → None。

    纯取值:构建在 init_langfuse()(env 就绪后)完成,这里不懒建,杜绝顺序陷阱。
    handler 无状态(归因走每请求 config),并发复用安全。
    """
    return _handler

def shutdown_langfuse() -> None:
    """进程退出前 flush 残留 trace(关机那批不丢)。lifespan finally 调用。"""
    if not _langfuse_configured():
        return

    from langfuse import get_client
    get_client().shutdown()






