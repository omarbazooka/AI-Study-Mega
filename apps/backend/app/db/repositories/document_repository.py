from typing import Dict, Any, Optional
import logging
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Get the Supabase client
supabase = get_supabase_client()

async def create_document(
    user_id: str,
    original_filename: str,
    file_size: int,
    file_hash: str,
    file_type: str = "pdf"
) -> Dict[str, Any]:
    """
    Creates a new document row with status 'uploaded' in the PostgreSQL database.
    """
    print(f"[DB] Creating document metadata row for {original_filename} (hash: {file_hash[:10]}...)")
    response = supabase.table("documents").insert({
        "user_id": user_id,
        "original_filename": original_filename,
        "file_size": file_size,
        "file_hash": file_hash,
        "file_type": file_type,
        "upload_status": "uploaded"
    }).execute()
    
    if not response.data:
        logger.warning("[DB] create_document returned empty data. Check database RLS policies.")
        return {}
    return response.data[0]

async def get_by_id(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a document by its primary key ID.
    """
    response = supabase.table("documents").select("*").eq("id", document_id).execute()
    return response.data[0] if response.data else None

async def get_by_hash(user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a document by user_id and file_hash (used for duplicate checks).
    """
    response = (
        supabase.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .eq("file_hash", file_hash)
        .execute()
    )
    return response.data[0] if response.data else None

async def update_storage_path(document_id: str, storage_path: str, upload_status: str) -> Dict[str, Any]:
    """
    Updates the storage path and status for a document.
    """
    print(f"[DB] Updating storage path for doc {document_id} to '{storage_path}' (status: {upload_status})")
    response = (
        supabase.table("documents")
        .update({
            "storage_path": storage_path,
            "upload_status": upload_status,
            "updated_at": "now()"
        })
        .eq("id", document_id)
        .execute()
    )
    if not response.data:
        logger.warning(f"[DB] update_storage_path for doc {document_id} returned empty data.")
        return {}
    return response.data[0]

async def update_status(document_id: str, status: str) -> Dict[str, Any]:
    """
    Updates the upload status of a document.
    """
    print(f"[DB] Updating status for doc {document_id} to: {status}")
    response = (
        supabase.table("documents")
        .update({
            "upload_status": status,
            "updated_at": "now()"
        })
        .eq("id", document_id)
        .execute()
    )
    if not response.data:
        logger.warning(f"[DB] update_status for doc {document_id} returned empty data.")
        return {}
    return response.data[0]

async def mark_ready(document_id: str, page_count: int, chunk_count: int) -> Dict[str, Any]:
    """
    Marks the document as ready and updates total page/chunk counts.
    """
    print(f"[DB] Marking doc {document_id} as READY (pages: {page_count}, chunks: {chunk_count})")
    response = (
        supabase.table("documents")
        .update({
            "upload_status": "ready",
            "page_count": page_count,
            "chunk_count": chunk_count,
            "updated_at": "now()"
        })
        .eq("id", document_id)
        .execute()
    )
    if not response.data:
        logger.warning(f"[DB] mark_ready for doc {document_id} returned empty data.")
        return {}
    return response.data[0]

async def mark_failed(document_id: str, error_message: str) -> Dict[str, Any]:
    """
    Marks the document as failed and logs the error message.
    """
    print(f"[DB] Marking doc {document_id} as FAILED. Reason: {error_message}")
    response = (
        supabase.table("documents")
        .update({
            "upload_status": "failed",
            "error_message": error_message,
            "updated_at": "now()"
        })
        .eq("id", document_id)
        .execute()
    )
    if not response.data:
        logger.warning(f"[DB] mark_failed for doc {document_id} returned empty data.")
        return {}
    return response.data[0]
