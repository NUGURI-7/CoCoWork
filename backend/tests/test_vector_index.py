"""HNSW 部分索引与检索 SQL 的写法对齐。"""
from uuid import UUID

import pytest

from app.services.knowledge.retrieval.sql import load_sql
from app.services.knowledge.retrieval.vector_index import (
    HNSW_MAX_DIM,
    create_hnsw_index_sql,
    hnsw_index_name,
    supports_hnsw,
    vector_type,
)

KB_ID = UUID("019f6557-07f6-7562-8f89-79662490b257")


@pytest.mark.parametrize("dim", [768, 1024, 1536, HNSW_MAX_DIM])
def test_search_sql_and_index_share_cast(dim: int) -> None:
    sql = load_sql("vector_search").format(vector_type=vector_type(dim))
    ddl = create_hnsw_index_sql(KB_ID, dim)

    cast = f"embedding::vector({dim})"
    assert f"ORDER BY e.{cast} <=> $1::vector({dim})" in sql
    assert f"(({cast}) vector_cosine_ops)" in ddl


def test_index_ddl_shape() -> None:
    ddl = create_hnsw_index_sql(KB_ID, 1024)

    assert ddl.startswith(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {hnsw_index_name(KB_ID)} ")
    assert "USING hnsw" in ddl
    assert ddl.endswith(f"WHERE knowledge_base_id = '{KB_ID}'")


def test_index_name_fits_pg_identifier_limit() -> None:
    assert len(hnsw_index_name(KB_ID)) <= 63


def test_dim_over_limit_is_rejected() -> None:
    assert supports_hnsw(HNSW_MAX_DIM)
    assert not supports_hnsw(HNSW_MAX_DIM + 1)
    with pytest.raises(ValueError):
        create_hnsw_index_sql(KB_ID, 4096)
