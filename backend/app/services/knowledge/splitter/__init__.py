"""Splitter 模块对外入口。

业务侧只 `from app.services.knowledge.splitter import splitter`，
不感知具体实现。v2 切换 = 改下面这行装配 + 移除旧依赖。
"""

from app.services.knowledge.splitter.base import Splitter
from app.services.knowledge.splitter.langchain_impl import LangChainSplitter

# 模块级单例。装配硬编码（splitter 不是部署变量，不入 env）
splitter: Splitter = LangChainSplitter()

__all__ = ["Splitter", "splitter"]