-- 向量检索(父子块):HNSW 捞候选 → 按段去重 → 阈值过滤 → top_k
-- 占位符:{dim} = 库锁定的向量维度(类型修饰符,PG 不许参数化,Python 端 format 拼入)
-- $1 query 向量  $2 kb_id  $3 相似度阈值  $4 top_k  $5 候选池大小
-- 注意:ORDER BY 的 cast 表达式必须与 HNSW 索引定义逐字一致,否则不命中索引

WITH nearest AS (SELECT e.paragraph_id,
                        e.document_id,
                        e.text AS chunk_text,
                        e.embedding::vector({dim}) <=> $1::vector({dim}) AS distance
FROM embeddings e
WHERE e.knowledge_base_id = $2 AND e.source_type = 'content'
ORDER BY e.embedding::vector({dim}) <=> $1::vector({dim})
    LIMIT $5
    ),
    dedup AS (
SELECT DISTINCT
ON (n.paragraph_id)
    n.paragraph_id, n.document_id, n.chunk_text, n.distance
FROM nearest n
ORDER BY n.paragraph_id, n.distance
    )

SELECT d.paragraph_id,
       d.document_id,
       doc.name AS doc_name,
       p.content,
       p.title,
       d.chunk_text,
       d.distance
FROM dedup d
         JOIN paragraphs p ON p.id = d.paragraph_id
         JOIN documents doc ON doc.id = d.document_id
WHERE (1 - d.distance) >= $3
ORDER BY d.distance LIMIT $4