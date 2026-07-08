import logging
from typing import List, Dict, Any
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Get the Supabase client
supabase = get_supabase_client()

async def insert_chunks(
    document_id: str,
    user_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]]
) -> List[Dict[str, Any]]:
    """
    Inserts a list of document chunks and their corresponding embeddings into the database.
    Batches database writes in chunks of 50 to prevent statement timeouts.
    """
    rows = []
    for idx, chunk in enumerate(chunks):
        rows.append({
            "document_id": document_id,
            "user_id": user_id,
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "metadata": chunk["metadata"],
            "embedding": embeddings[idx]
        })
    
    inserted_data = []
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        print(f"[DB] Inserting chunk batch {i // batch_size + 1}/{((len(rows)-1)//batch_size)+1} ({len(batch)} rows)...")
        response = supabase.table("document_chunks").insert(batch).execute()
        if response.data:
            inserted_data.extend(response.data)
            
    return inserted_data

async def delete_chunks_by_document(document_id: str) -> List[Dict[str, Any]]:
    """
    Deletes all chunks associated with a specific document.
    """
    response = supabase.table("document_chunks").delete().eq("document_id", document_id).execute()
    return response.data

async def get_chunks_by_document(document_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all chunks of a document ordered by their indexing sequence.
    """
    response = (
        supabase.table("document_chunks")
        .select("*")
        .eq("document_id", document_id)
        .order("chunk_index", desc=False)
        .execute()
    )
    return response.data


# ── Retrieval module integration ─────────────────────────────────────────────
# These two methods satisfy VectorChunkRepositoryProtocol / KeywordChunkRepositoryProtocol
# from app.ai_system.retrieval, and are the bridge between the RAG retrieval module and the
# real document_chunks table (see migration 005_document_chunk_retrieval.sql for the RPCs).

async def search_vector_chunks(
    *, user_id: str, document_id: str, query_embedding: List[float],
    match_count: int, filters: Dict[str, Any], similarity_threshold: float
) -> List[Dict[str, Any]]:
    """Semantic vector search over document_chunks, scoped to one user + document."""
    try:
        response = supabase.rpc("match_document_chunks", {
            "query_embedding": query_embedding,
            "match_threshold": similarity_threshold,
            "match_count": match_count,
            "p_user_id": user_id,
            "p_document_id": document_id,
        }).execute()
        rows = response.data or []
    except Exception as e:
        logger.error(f"[DB] Vector chunk search failed: {str(e)}")
        return []

    return [_apply_metadata_filters(row, filters) for row in rows if _apply_metadata_filters(row, filters)]


async def search_keyword_chunks(
    *, user_id: str, document_id: str, query: str,
    match_count: int, filters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Trigram/ILIKE keyword search over document_chunks, scoped to one user + document."""
    try:
        response = supabase.rpc("search_document_chunks_keyword", {
            "p_query": query,
            "match_count": match_count,
            "p_user_id": user_id,
            "p_document_id": document_id,
        }).execute()
        rows = response.data or []
    except Exception as e:
        logger.error(f"[DB] Keyword chunk search failed: {str(e)}")
        return []

    return [_apply_metadata_filters(row, filters) for row in rows if _apply_metadata_filters(row, filters)]


def _apply_metadata_filters(row: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies any extracted MetadataFilters (page_number, chapter, section_title, ...) as a
    post-filter, since document_chunks has no section_title column yet — only page_start/
    page_end and a free-form metadata jsonb blob. Returns the row unchanged if it passes,
    or {} if it should be excluded.
    """
    if not filters:
        return row
    page_number = filters.get("page_number")
    if page_number is not None:
        page_start = row.get("page_start")
        page_end = row.get("page_end") or page_start
        if page_start is None or not (page_start <= page_number <= page_end):
            return {}
    return row
