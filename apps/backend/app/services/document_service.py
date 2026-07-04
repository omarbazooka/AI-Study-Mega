import hashlib
from fastapi import UploadFile, BackgroundTasks
from app.ai_system.ingestion.document_validator import validate_pdf
from app.db.repositories import document_repository
from app.db.supabase_client import get_supabase_client
from app.core.config import settings
from app.workers.document_worker import run_document_ingestion
from typing import Dict, Any

async def upload_and_ingest_document(
    user_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Orchestrates the document upload flow:
    1. Read and validate the raw PDF bytes.
    2. Compute file SHA256 hash.
    3. Check for duplicates (same user_id + file_hash).
    4. Create document record with status 'uploaded'.
    5. Upload PDF file to Supabase Storage.
    6. Update document record storage path and status to 'stored'.
    7. Trigger BackgroundTask to run parser, chunker, embedding, and save.
    """
    # 1. Read file content into memory bytes
    file_bytes = await file.read()
    
    # 2. Run validations (throws ValueError if invalid)
    validate_pdf(file_bytes, file.filename, file.content_type)
    
    # 3. Compute SHA256 hash for duplicate detection
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # 4. Check for duplicate upload by the same user
    existing_doc = await document_repository.get_by_hash(user_id, file_hash)
    if existing_doc:
        return {
            "document_id": existing_doc["id"],
            "status": existing_doc["upload_status"],
            "message": "Document already uploaded.",
            "is_duplicate": True
        }
        
    # 5. Create document metadata record in DB
    doc = await document_repository.create_document(
        user_id=user_id,
        original_filename=file.filename,
        file_size=len(file_bytes),
        file_hash=file_hash,
        file_type="pdf"
    )
    doc_id = doc["id"]
    
    # 6. Upload PDF to Supabase Storage
    storage_path = f"users/{user_id}/documents/{doc_id}/{doc_id}.pdf"
    supabase = get_supabase_client()
    
    try:
        # upload parameters: path, file (bytes), file_options (content-type metadata)
        supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
    except Exception as e:
        # Mark document failed if the storage upload fails
        await document_repository.mark_failed(doc_id, f"Storage upload error: {str(e)}")
        raise RuntimeError(f"Supabase storage upload failed: {str(e)}")
        
    # 7. Update document record to reflect storage location and 'stored' status
    await document_repository.update_storage_path(
        document_id=doc_id,
        storage_path=storage_path,
        upload_status="stored"
    )
    
    # 8. Start async background ingestion via FastAPI BackgroundTasks
    background_tasks.add_task(run_document_ingestion, doc_id)
    
    return {
        "document_id": doc_id,
        "status": "processing",
        "message": "Document uploaded successfully and is being processed.",
        "is_duplicate": False
    }
