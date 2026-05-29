"""LangChain RecursiveCharacterTextSplitter 适配。

v1 baseline。已知局限（语义盲、中英不等价、跨块断裂）见决策 §13.3；
v2 自研对照见 §13.4。
"""
from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter.base import Splitter
from langchain_text_splitters import RecursiveCharacterTextSplitter


class LangChainSplitter(Splitter):
    """包一层 RecursiveCharacterTextSplitter，按 ChunkConfig 实例化。"""

    def split(self, text: str, config: ChunkConfig) -> list[str]:
        if not text:
            return []
        impl = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.overlap
        )
        return impl.split_text(text)

