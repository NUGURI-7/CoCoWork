"""按句子边界切块：断句 → 逐句上攒 → 到 token 上限封口。

与 `LangChainSplitter` 的根本区别在**方向**：那边拿整段往下切，切不动了按字符
硬劈，切口会落在句子中间；这边先把文本打散成句子，再自底向上攒，**切口永远落
在句末标点上**。

计数用 tiktoken（cl100k_base）。它数的不是 embedding 模型实际的 token——那个
拿不到（`kb.embedding_model` 由用户配置，API 模型不暴露分词器）——要的是一把
**刻度稳定**的尺子：同一个 `chunk_size`，中文和英文文档装进去的信息量大致相当，
换 embedding 模型也不必改这个数。
"""
import re

import tiktoken

from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter.base import Splitter

# 句末标点（中英文都收，语料语言不受控）+ 尾随的收尾引号括号，或连续换行。
# 断句只在这些位置发生；收尾符号并入前一句，避免切出 `」` 开头的碎片。
_SENTENCE_END = re.compile(r"""[。！？；!?;]+[」』”’"')）]*|\n+""")

_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    """懒加载编码表。

    不在模块级初始化：首次调用要读约 1.6MB 的编码文件，缺失时会联网下载，
    放在 import 期等于让应用启动依赖网络。镜像构建时已预下，运行时命中本地缓存。
    """
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def _count(text: str) -> int:
    return len(_get_encoder().encode(text))


def _split_sentences(text: str) -> list[str]:
    """切成句子。**拼回去逐字等于原文**——`Embedding.text` 要拿它定位回段落原文，
    丢了空白就对不上了，故纯空白片段不丢弃，而是并到下一句开头。
    """
    out: list[str] = []
    start = 0
    pending = ""
    for m in _SENTENCE_END.finditer(text):
        piece = text[start:m.end()]
        start = m.end()
        if piece.strip():
            out.append(pending + piece)
            pending = ""
        else:
            pending += piece
    tail = pending + text[start:]
    if tail.strip():
        out.append(tail)
    return out


def _hard_split(sentence: str, size: int) -> list[str]:
    """单句超上限时按 token 均分。**全模块只有这条路会切断句子**——无标点长文、
    整行表格这类没有下刀点，不切就会产出超限的块。
    切点落在 token 边界上，可能劈开一个多字节汉字（decode 出替换符），
    这是兜底路径的固有代价。
    """
    encoder = _get_encoder()
    ids = encoder.encode(sentence)
    return [encoder.decode(ids[i:i + size]) for i in range(0, len(ids), size)]


def _overlap_tail(sentences: list[str], overlap: int, limit: int) -> tuple[list[str], int]:
    """从已封口的块尾部往回捞若干**完整句子**，垫到下一块开头。

    语义是「**至少**覆盖 overlap」而非「不超过 overlap」：句子长度不受控，
    中文一句常在 25~50 token，按上限收的话，配 overlap=20 会几乎永远捞不到
    任何句子，这个参数就形同虚设。故向上取整到句子边界。

    `limit` 是硬顶（半块）：防止一个超长句把下一块开局就占满，退化成一串
    内容高度重复的小块。
    """
    if overlap <= 0:
        return [], 0
    tail: list[str] = []
    total = 0
    for sent in reversed(sentences):
        n = _count(sent)
        if not tail and n > limit:
            # 末句本身就超过硬顶：带上它下一块开局就废掉大半，
            # 而它已完整落在上一块里，语义并没有丢
            return [], 0
        if tail and total + n > limit:
            break
        tail.insert(0, sent)
        total += n
        if total >= overlap:
            break
    return tail, total


class SentenceSplitter(Splitter):
    """断句 + 向上合并。`chunk_size` / `overlap` 均以 token 计。"""

    def split(self, text: str, config: ChunkConfig) -> list[str]:
        if not text:
            return []

        size = config.chunk_size
        limit = size // 2  # overlap 实际带回量的硬顶

        sentences: list[str] = []
        for raw in _split_sentences(text):
            sentences.extend(_hard_split(raw, size) if _count(raw) > size else [raw])

        chunks: list[str] = []
        cur: list[str] = []
        cur_tokens = 0
        for sent in sentences:
            n = _count(sent)
            if cur and cur_tokens + n > size:
                chunks.append("".join(cur))
                cur, cur_tokens = _overlap_tail(cur, config.overlap, limit)
                if cur_tokens + n > size:
                    # 垫回的尾巴加上这一句仍然超限。**上限优先于 overlap**：
                    # 尾巴只是锦上添花，chunk_size 是对用户的承诺，不能破。
                    cur, cur_tokens = [], 0
            cur.append(sent)
            cur_tokens += n
        if cur:
            chunks.append("".join(cur))
        return chunks
