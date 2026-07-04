from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status
from app.schemas.document_schema import UploadResponse, StatusResponse
from app.services.document_service import upload_and_ingest_document
from app.db.repositories import document_repository

router = APIRouter(prefix="/documents", tags=["documents"])

# Placeholder static User ID for authentication context
MOCK_USER_ID = "00000000-0000-0000-0000-000000000000"

async def get_current_user() -> str:
    """
    TODO: Integrate this placeholder with the actual Supabase JWT authentication system
    to retrieve the authenticated user's ID from tokens.
    """
    return MOCK_USER_ID

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Upload a PDF document.
    Validates, saves metadata, uploads to Supabase storage, and starts background ingestion.
    Returns status immediately.
    """
    try:
        result = await upload_and_ingest_document(user_id, file, background_tasks)
        
        # Determine the user message based on whether it is a duplicate upload
        message = (
            "Document already uploaded." 
            if result.get("is_duplicate") 
            else "Document uploaded successfully and is being processed."
        )
        
        return UploadResponse(
            document_id=result["document_id"],
            status=result["status"],
            message=message
        )
    except ValueError as ve:
        # File validation errors (e.g. wrong size/format)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        # Internal server/storage errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )

@router.get("/{document_id}/status", response_model=StatusResponse)
async def get_document_status(
    document_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Exposes document status for frontend polling.
    Allows tracking pipeline progress through stages: uploaded, parsing, chunking, embedding, ready, failed.
    """
    doc = await document_repository.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    # Verify ownership to ensure users can only view their own documents
    if str(doc["user_id"]) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to access this document's status."
        )
        
    return StatusResponse(
        document_id=doc["id"],
        status=doc["upload_status"],
        page_count=doc.get("page_count"),
        chunk_count=doc.get("chunk_count") or 0,
        error_message=doc.get("error_message")
    )
