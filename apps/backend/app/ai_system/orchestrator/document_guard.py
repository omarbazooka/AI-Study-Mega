from typing import Dict, Any
from app.db.repositories import document_repository
from app.db.repositories.chunk_repository import get_chunks_by_document
from app.ai_system.orchestrator.errors import (
    DocumentNotFoundError,
    DocumentAccessDeniedError,
    DocumentNotReadyError
)

async def validate_document_access(document_id: str, user_id: str) -> Dict[str, Any]:
    """
    Validates that a document exists, belongs to the requesting user,
    and has been fully processed (status is 'ready', chunk_count > 0,
    has database chunks, and embeddings exist).

    Args:
        document_id: The UUID of the document.
        user_id: The UUID of the requesting user.

    Returns:
        Dict[str, Any]: The document record from the database.

    Raises:
        DocumentNotFoundError: If the document is not found.
        DocumentAccessDeniedError: If the document does not belong to the user.
        DocumentNotReadyError: If the document is not processed yet or has no chunks/embeddings.
    """
    doc = await document_repository.get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundError("DOCUMENT_NOT_FOUND")

    # Verify ownership
    if str(doc.get("user_id")) != str(user_id):
        raise DocumentAccessDeniedError("DOCUMENT_ACCESS_DENIED")

    # Verify ingestion status is exactly "ready"
    status = doc.get("upload_status")
    if status != "ready":
        raise DocumentNotReadyError("DOCUMENT_NOT_READY")

    # Ensure document actually has chunks indexed in metadata
    chunk_count = doc.get("chunk_count") or 0
    if chunk_count <= 0:
        raise DocumentNotReadyError("DOCUMENT_NOT_READY")

    try:
        chunks = await get_chunks_by_document(document_id)
    except Exception:
        raise DocumentNotReadyError("DOCUMENT_NOT_READY")
        
    if not chunks:
        raise DocumentNotReadyError("DOCUMENT_NOT_READY")

    if not any(c.get("embedding") is not None for c in chunks):
        raise DocumentNotReadyError("DOCUMENT_NOT_READY")

    return doc
