-- Retrieval indexes for Supabase PostgreSQL + pgvector.
-- Assumes a chunks table with: id, document_id, user_id, raw_text, metadata, embedding, page_number, section_title.

create extension if not exists vector;
create extension if not exists pg_trgm;

create index if not exists idx_chunks_document_user
on chunks (document_id, user_id);

create index if not exists idx_chunks_page
on chunks (document_id, page_number);

create index if not exists idx_chunks_section_trgm
on chunks using gin (section_title gin_trgm_ops);

create index if not exists idx_chunks_metadata_gin
on chunks using gin (metadata);

create index if not exists idx_chunks_raw_text_trgm
on chunks using gin (raw_text gin_trgm_ops);

-- Use the correct vector dimension in the original table definition.
-- This index works when chunks.embedding is a pgvector column.
create index if not exists idx_chunks_embedding_hnsw
on chunks using hnsw (embedding vector_cosine_ops);
