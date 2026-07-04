-- Migration: Initialize documents and document_chunks tables
-- This migration script sets up pgvector and the core tables for the document pipeline.

-- Enable pgvector and uuid-ossp extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents metadata table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT,
    file_type TEXT NOT NULL DEFAULT 'pdf',
    file_size BIGINT NOT NULL,
    file_hash TEXT NOT NULL,
    upload_status TEXT NOT NULL DEFAULT 'uploaded', -- uploaded, validating, stored, parsing, chunking, embedding, ready, failed
    page_count INTEGER,
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_user_document_hash UNIQUE (user_id, file_hash)
);

-- Create document_chunks table
-- WARNING: The embedding vector dimension is hardcoded to 384 here to match the default
-- embedding model "all-MiniLM-L6-v2". If you change the embedding model to one that
-- returns a different number of dimensions (e.g., OpenAI text-embedding-3-small at 1536),
-- you MUST change the vector dimension (e.g. vector(1536)) in the DB schema.
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create HNSW index for high-performance semantic search using cosine distance
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
ON document_chunks
USING hnsw (embedding vector_cosine_ops);
