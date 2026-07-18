"""中文分词收口。

全文检索的分词口径统一从这里出，口径调整（自定义词库、归一化规则）只改这一处：
- 写入侧（文档处理、批量导入回填）用 ``tokenize``：全量收词，求全；
- 查询侧（keyword 检索）用 ``tokenize_query``：TF-IDF 关键词提取，求精。
索引全量、查询精锐的不对称是刻意的——索引要「什么都可能被查到」，
查询要「别把废词带进来」（Dify 同款姿势）。
"""

from __future__ import annotations

import re

import jieba
import jieba.analyse

from app.services.knowledge.stopwords import STOPWORDS

_NON_WORD_RE = re.compile(r"\W+")


def tokenize(text: str) -> list[str]:
    """文本 → 词序列（搜索引擎模式 + 小写归一化，过滤纯标点/空白）。

    - ``cut_for_search``：在精确切分的基础上把长词再切细，提高召回；
      索引侧和查询侧必须走同一个函数，切法对不上等于白建索引。
    - ``lower()``：tsvector 字面量直写绕过了 simple 词典的小写归一化，
      在这里补上，否则大写词（如 CT）永远查不到。
    """

    tokens: list[str] = []
    for token in jieba.cut_for_search(text):
        token = token.strip().lower()
        if not token or token in STOPWORDS or _NON_WORD_RE.fullmatch(token):
            continue
        tokens.append(token)
    return tokens


QUERY_TOP_K = 10


def tokenize_query(text: str, top_k: int = QUERY_TOP_K) -> list[str]:
    """query 侧分词：TF-IDF 关键词提取，只留最有信息量的前 K 个词。

    索引侧口径（tokenize）不动，本函数只决定「拿哪些词去查」——PG 的
    ts_rank 没有 IDF，就在查询侧提前替它把废词筛掉（IDF 用 jieba 内置
    通用词典 idf.txt）。extract_tags 默认丢单字词，「左/后/头」这类噪声
    顺带清掉；jieba 自带停用词表只有英文，中文废词（如「这些」）会漏网，
    故提取结果仍过一遍小写 + 停用词 + 标点，与索引侧归一化口径保持一致。
    """

    tokens: list[str] = []
    for token in jieba.analyse.extract_tags(text, topK=top_k):
        token = token.strip().lower()
        if not token or token in STOPWORDS or _NON_WORD_RE.fullmatch(token):
            continue
        tokens.append(token)
    return tokens
