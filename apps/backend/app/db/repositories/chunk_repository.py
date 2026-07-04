from typing import List, Dict, Any
from app.db.supabase_client import get_supabase_client

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
    
    Args:
        document_id: The UUID of the parent document.
        user_id: The UUID of the owner.
        chunks: List of dictionaries containing index, content, page ranges, and metadata.
        embeddings: List of embedding vectors (list of floats).
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
    
    # Supabase Postgrest API supports batch inserts directly
    response = supabase.table("document_chunks").insert(rows).execute()
    return response.data

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
