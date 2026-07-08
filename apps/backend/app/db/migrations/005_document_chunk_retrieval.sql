-- Migration 005: Retrieval support for document_chunks (RAG retrieval <-> memory integration)
--
-- 002_add_retrieval_indexes.sql was written against a table called `chunks` that does not
-- exist in this project; the real table created in 001_init_documents.sql is `document_chunks`
-- (content, page_start, page_end, no section_title). This migration adds the indexes and the
-- RPC function actually needed by app/db/repositories/chunk_repository.py against that table.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- Trigram index to speed up ILIKE / similarity-based keyword search on chunk content
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_trgm
ON document_chunks USING gin (content gin_trgm_ops);

-- Composite index for scoping keyword/vector search to a user's document
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_user
ON document_chunks (document_id, user_id);

-- Vector similarity search RPC, scoped to a single user + document (mirrors match_memory_items
-- from 003_update_embedding_dimension.sql so both retrieval paths behave consistently).
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1024),
    match_threshold float,
    match_count int,
    p_user_id uuid,
    p_document_id uuid
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    user_id uuid,
    chunk_index int,
    content text,
    page_start int,
    page_end int,
    metadata jsonb,
    similarity numeric
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.user_id,
        c.chunk_index,
        c.content,
        c.page_start,
        c.page_end,
        c.metadata,
        (1 - (c.embedding <=> query_embedding))::numeric AS similarity
    FROM document_chunks c
    WHERE c.user_id = p_user_id
      AND c.document_id = p_document_id
      AND c.embedding IS NOT NULL
      AND (1 - (c.embedding <=> query_embedding)) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Keyword search RPC using trigram similarity, scoped to a single user + document.
-- Falls back gracefully to 0 rows if p_query is empty (caller should already skip this case).
CREATE OR REPLACE FUNCTION search_document_chunks_keyword(
    p_query text,
    match_count int,
    p_user_id uuid,
    p_document_id uuid
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    user_id uuid,
    chunk_index int,
    content text,
    page_start int,
    page_end int,
    metadata jsonb,
    rank numeric
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.user_id,
        c.chunk_index,
        c.content,
        c.page_start,
        c.page_end,
        c.metadata,
        similarity(c.content, p_query)::numeric AS rank
    FROM document_chunks c
    WHERE c.user_id = p_user_id
      AND c.document_id = p_document_id
      AND (c.content ILIKE '%' || p_query || '%' OR similarity(c.content, p_query) > 0.1)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$;
