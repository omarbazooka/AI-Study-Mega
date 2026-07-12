from typing import Dict, Any, Optional
from fastapi import HTTPException
import logging
from app.db.repositories import chat_repository, document_repository

logger = logging.getLogger(__name__)

async def validate_session_ownership_and_document(
    session_id: str, 
    document_id: str, 
    user_id: str,
    create_if_missing: bool = False
) -> Dict[str, Any]:
    """
    Validates:
    1. The session exists.
    2. The session belongs to the authenticated user.
    3. The session is linked to the requested document.
    4. Reject legacy NULL document sessions.
    """
    import uuid

    # Check if session_id is a valid UUID
    try:
        uuid.UUID(session_id)
    except ValueError:
        logger.warning(f"Session {session_id} is not a valid UUID.")
        raise HTTPException(status_code=400, detail="INVALID_SESSION_UUID")

    session = await chat_repository.get_chat_session(session_id)
    if not session:
        if not create_if_missing:
            logger.warning(f"Session {session_id} not found.")
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

        # Validate that the user owns the document before creating the session on the fly
        doc = await document_repository.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
        if str(doc.get("user_id")) != str(user_id):
            raise HTTPException(status_code=403, detail="DOCUMENT_ACCESS_DENIED")
        
        session = await chat_repository.create_chat_session(user_id, session_id, document_id)
        
    if str(session.get("user_id")) != str(user_id):
        logger.warning(f"Session {session_id} owner mismatch: {session.get('user_id')} != {user_id}")
        raise HTTPException(status_code=403, detail="SESSION_ACCESS_DENIED")
        
    session_doc_id = session.get("document_id")
    if not session_doc_id:
        logger.warning(f"Session {session_id} has no linked document (legacy session).")
        raise HTTPException(status_code=400, detail="LEGACY_SESSION_REJECTED")
        
    if str(session_doc_id) != str(document_id):
        logger.warning(f"Session {session_id} document mismatch: {session_doc_id} != {document_id}")
        raise HTTPException(status_code=400, detail="SESSION_DOCUMENT_MISMATCH")
        
    return session

async def create_document_scoped_session(
    user_id: str, 
    document_id: str, 
    session_id: str
) -> Dict[str, Any]:
    """
    Creates a new chat session scoped specifically to document_id, 
    checking user ownership of the document first.
    """
    # Verify document ownership first
    doc = await document_repository.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
        
    if str(doc.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="DOCUMENT_ACCESS_DENIED")
        
    # Check if session already exists
    existing = await chat_repository.get_chat_session(session_id)
    if existing:
        # Validate that existing session belongs to the same user and document
        if str(existing.get("user_id")) != str(user_id):
            raise HTTPException(status_code=403, detail="SESSION_ACCESS_DENIED")
        existing_doc = existing.get("document_id")
        if not existing_doc or str(existing_doc) != str(document_id):
            raise HTTPException(status_code=400, detail="SESSION_DOCUMENT_MISMATCH")
        return existing
        
    # Session does not exist; create it scoped to this document
    session = await chat_repository.create_chat_session(user_id, session_id, document_id)
    return session
