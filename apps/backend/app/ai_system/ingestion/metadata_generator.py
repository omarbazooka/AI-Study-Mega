from typing import Dict, Any

def generate_chunk_metadata(
    document_id: str,
    filename: str,
    chunk_index: int,
    page_start: int,
    page_end: int,
    source_type: str = "pdf"
) -> Dict[str, Any]:
    """
    Generates a metadata dictionary for a single document chunk.
    This metadata is stored alongside the chunk in PostgreSQL + pgvector.
    """
    return {
        "document_id": document_id,
        "filename": filename,
        "source_type": source_type,
        "chunk_index": chunk_index,
        "page_start": page_start,
        "page_end": page_end
    }
