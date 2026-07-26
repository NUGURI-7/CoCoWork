-- 全文检索:分词后的 query OR 匹配 → ts_rank_cd 打分 → 阈值 → top_k
-- $1 kb_id  $2 tsquery 字面量(如 '大便' | '干结',Python 端已转义)  $3 分数阈值  $4 top_k


WITH matched AS (SELECT p.id                                   AS paragraph_id,
                        p.document_id,
                        p.content,
                        p.title,
                        ts_rank_cd(p.search_vector, query, 32) AS score
                 FROM paragraphs p,
                      to_tsquery('simple', $2) AS query
                 WHERE p.knowledge_base_id = $1
                   AND p.search_vector @@ query
    )


SELECT m.paragraph_id,
       m.document_id,
       doc.name AS doc_name,
       m.content,
       m.title,
       m.score
FROM matched m
         JOIN documents doc ON doc.id = m.document_id
WHERE m.score >= $3
ORDER BY m.score DESC LIMIT $4


