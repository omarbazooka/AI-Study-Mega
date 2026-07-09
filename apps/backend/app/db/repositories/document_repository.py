import logging
from typing import Dict, Any, Optional
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Get the Supabase client
supabase = get_supabase_client()

# In-memory document storage fallback
IN_MEMORY_DOCS = {}

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
    try:
        response = supabase.table("documents").insert({
            "user_id": user_id,
            "original_filename": original_filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "file_type": file_type,
            "upload_status": "uploaded"
        }).execute()
        
        if response.data:
            doc = response.data[0]
            IN_MEMORY_DOCS[doc["id"]] = doc
            return doc
    except Exception as e:
        logger.warning(f"[DB] Database insert failed, falling back to in-memory: {e}")
        
    import uuid
    from datetime import datetime, timezone
    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "user_id": user_id,
        "original_filename": original_filename,
        "file_size": file_size,
        "file_hash": file_hash,
        "file_type": file_type,
        "upload_status": "uploaded",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    IN_MEMORY_DOCS[doc_id] = doc
    return doc

async def get_by_id(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a document by its primary key ID.
    """
    try:
        response = supabase.table("documents").select("*").eq("id", document_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.warning(f"[DB] Database get failed, checking in-memory: {e}")
    return IN_MEMORY_DOCS.get(document_id)

async def get_by_hash(user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a document by user_id and file_hash (used for duplicate checks).
    """
    try:
        response = (
            supabase.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .eq("file_hash", file_hash)
            .execute()
        )
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.warning(f"[DB] Database get_by_hash failed, checking in-memory: {e}")
    for doc in IN_MEMORY_DOCS.values():
        if doc.get("user_id") == user_id and doc.get("file_hash") == file_hash:
            return doc
    return None

async def update_storage_path(document_id: str, storage_path: str, upload_status: str) -> Dict[str, Any]:
    """
    Updates the storage path and status for a document.
    """
    print(f"[DB] Updating storage path for doc {document_id} to '{storage_path}' (status: {upload_status})")
    try:
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
        if response.data:
            doc = response.data[0]
            IN_MEMORY_DOCS[document_id] = doc
            return doc
    except Exception as e:
        logger.warning(f"[DB] Database update_storage_path failed, using in-memory: {e}")
    doc = IN_MEMORY_DOCS.get(document_id)
    if doc:
        doc["storage_path"] = storage_path
        doc["upload_status"] = upload_status
        return doc
    return {}

async def update_status(document_id: str, status: str) -> Dict[str, Any]:
    """
    Updates the upload status of a document.
    """
    print(f"[DB] Updating status for doc {document_id} to: {status}")
    try:
        response = (
            supabase.table("documents")
            .update({
                "upload_status": status,
                "updated_at": "now()"
            })
            .eq("id", document_id)
            .execute()
        )
        if response.data:
            doc = response.data[0]
            IN_MEMORY_DOCS[document_id] = doc
            return doc
    except Exception as e:
        logger.warning(f"[DB] Database update_status failed, using in-memory: {e}")
    doc = IN_MEMORY_DOCS.get(document_id)
    if doc:
        doc["upload_status"] = status
        return doc
    return {}

async def mark_ready(document_id: str, page_count: int, chunk_count: int) -> Dict[str, Any]:
    """
    Marks the document as ready and updates total page/chunk counts.
    """
    print(f"[DB] Marking doc {document_id} as READY (pages: {page_count}, chunks: {chunk_count})")
    doc = await get_by_id(document_id)
    processing_time_seconds = None
    if doc and doc.get("created_at"):
        from datetime import datetime, timezone
        try:
            created_at = datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            processing_time_seconds = round((now - created_at).total_seconds(), 2)
        except Exception as e:
            logger.error(f"Error calculating processing time on ready: {e}")

    try:
        response = (
            supabase.table("documents")
            .update({
                "upload_status": "ready",
                "page_count": page_count,
                "chunk_count": chunk_count,
                "processing_time_seconds": processing_time_seconds,
                "updated_at": "now()"
            })
            .eq("id", document_id)
            .execute()
        )
        if response.data:
            res_doc = response.data[0]
            IN_MEMORY_DOCS[document_id] = res_doc
            return res_doc
    except Exception as e:
        logger.warning(f"[DB] Database mark_ready failed, using in-memory: {e}")
        
    if doc:
        doc["upload_status"] = "ready"
        doc["page_count"] = page_count
        doc["chunk_count"] = chunk_count
        doc["processing_time_seconds"] = processing_time_seconds
        return doc
    return {}

async def mark_failed(document_id: str, error_message: str) -> Dict[str, Any]:
    """
    Marks the document as failed and logs the error message.
    """
    print(f"[DB] Marking doc {document_id} as FAILED. Reason: {error_message}")
    doc = await get_by_id(document_id)
    processing_time_seconds = None
    if doc and doc.get("created_at"):
        from datetime import datetime, timezone
        try:
            created_at = datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            processing_time_seconds = round((now - created_at).total_seconds(), 2)
        except Exception as e:
            logger.error(f"Error calculating processing time on fail: {e}")

    try:
        response = (
            supabase.table("documents")
            .update({
                "upload_status": "failed",
                "error_message": error_message,
                "processing_time_seconds": processing_time_seconds,
                "updated_at": "now()"
            })
            .eq("id", document_id)
            .execute()
        )
        if response.data:
            res_doc = response.data[0]
            IN_MEMORY_DOCS[document_id] = res_doc
            return res_doc
    except Exception as e:
        logger.warning(f"[DB] Database mark_failed failed, using in-memory: {e}")
        
    if doc:
        doc["upload_status"] = "failed"
        doc["error_message"] = error_message
        doc["processing_time_seconds"] = processing_time_seconds
        return doc
    return {}
