"""自定义 Tortoise 字段。

Tortoise 无原生 pgvector 支持，这里提供 ``VectorField`` 用于声明 pgvector 的
``vector`` 列。注意：相似度检索（``<=>`` 等距离算子）Tortoise 无法表达，
需走原生 SQL（见检索 service）。本字段只负责「建列 + Python<->DB 值转换」。
"""

from __future__ import annotations

import re
from typing import Any

from tortoise import Model
from tortoise.fields import Field


class VectorField(Field):
    """pgvector ``vector`` 列（**不锁维度**）。

    不写死维度（``vector`` 而非 ``vector(N)``），以兼容不同知识库使用不同
    embedding 模型、维度不同的向量同表存储。

    Python 侧用 ``list[float]``；与 DB 之间用 pgvector 的文本字面量
    ``[1,2,3]`` 互转（避免依赖 asyncpg 的 vector codec 注册）。写入向量时
    建议在原生 SQL 里显式 ``$1::vector(dims)`` 转换，确保命中按库建的索引。
    """

    SQL_TYPE = "vector"

    def to_db_value(self, value: list[float] | None, instance: Any) -> str | None:
        if value is None:
            return None
        return "[" + ",".join(str(float(x)) for x in value) + "]"

    def to_python_value(self, value: Any) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(x) for x in value]
        # DB 返回形如 "[1,2,3]" 的文本
        text = str(value).strip().strip("[]")
        if not text:
            return []
        return [float(x) for x in text.split(",")]

class TSVectorField(Field):
    """PG ``tsvector`` 列（全文检索的倒排索引物料）。

    Python 侧用 ``list[str]``（已分好的词序列，分词由上层 tokenizer 负责）；
    与 DB 之间用带位置的 tsvector 字面量 ``'词':1 '词':2`` 互转——位置信息
    是 ``ts_rank`` 排序的依据，裸文本入库会丢位置。与 ``VectorField`` 同款
    分工：本字段只负责「建列 + 值转换」，检索走原生 SQL。
    """

    SQL_TYPE = "tsvector"

    _LEXEME_RE = re.compile(r"'((?:''|[^'])*)':([\d,]+)")

    def to_db_value(self, value: list[str] | None, instance: Any) -> str | None:
        if value is None:
            return None
        parts: list[str] = []
        position = 0
        for token in value:
            token = token.strip()
            if not token:
                continue
            position += 1
            escaped = token.replace("\\", "\\\\").replace("'", "''")
            parts.append(f"'{escaped}':{position}")
        return " ".join(parts)

    def to_python_value(self, value: Any) -> list[str] | None:
        if value is None or isinstance(value, list):
            return value
        # DB 返回形如 "'大便':2,5 '单纯':1"（按词典序），还原成按位置排序的词序列
        positioned: list[tuple[int, str]] = []
        for lexeme, positions in self._LEXEME_RE.findall(str(value)):
            token = lexeme.replace("''", "'").replace("\\\\", "\\")
            for pos in positions.split(","):
                positioned.append((int(pos), token))
        return [token for _, token in sorted(positioned)]






