"""Splitter 抽象层。

v1 走 LangChain baseline，v2 计划自研对照（决策见
docs/design/knowledge-rag-decisions.md §13）。业务侧（process_document）只依赖
本 ABC 的 split 方法，切换实现不动业务代码。
"""

from abc import ABC, abstractmethod

from app.schemas.knowledge import ChunkConfig


class Splitter(ABC):
    """文本切块器接口：把整段文本切成子块列表。"""

    @abstractmethod
    def split(self, text: str, config: ChunkConfig) -> list[str]:
        """按配置切块。空文本返回 []。"""
        ...
