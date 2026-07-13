import os
import sys
import json
import hashlib
import asyncio
from datetime import datetime, timezone

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.config import settings
from app.db.repositories import document_repository
from app.db.supabase_client import get_supabase_client
from app.workers.document_worker import run_document_ingestion
from evaluation.runners.auth_helper import authenticate_evaluation_user

async def ingest_documents():
    print("[INGEST] Starting document verification and ingestion...")
    
    # 1. Verify exactly 3 PDFs exist in evaluation/documents
    doc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "documents"))
    if not os.path.exists(doc_dir):
        print(f"[INGEST] ERROR: Documents directory '{doc_dir}' does not exist.")
        sys.exit(1)
        
    pdf_files = [f for f in os.listdir(doc_dir) if f.lower().endswith(".pdf")]
    print(f"[INGEST] Found {len(pdf_files)} PDF files: {pdf_files}")
    
    if len(pdf_files) != 3:
        print(f"[INGEST] ERROR: Expected exactly 3 PDF files in '{doc_dir}', but found {len(pdf_files)}.")
        sys.exit(1)
        
    # 2. Authenticate the evaluation user
    try:
        user_id, access_token = authenticate_evaluation_user()
    except Exception as e:
        print(f"[INGEST] ERROR: Authentication failed: {e}")
        sys.exit(1)
        
    supabase = get_supabase_client()
    manifest_data = {}
    
    for filename in pdf_files:
        filepath = os.path.join(doc_dir, filename)
        
        # Calculate SHA-256 hash
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            file_bytes = f.read()
            sha256.update(file_bytes)
        file_hash = sha256.hexdigest()
        file_size = len(file_bytes)
        
        # Determine language from name
        if "arabic" in filename.lower() or "تلخيص" in filename.lower() or "document 2" in filename.lower():
            language = "ar"
        else:
            language = "en"
            
        print(f"\n[INGEST] Processing '{filename}' (Language: {language}, Size: {file_size} bytes, Hash: {file_hash[:10]}...)")
        
        # Check if already exists in DB
        existing_doc = await document_repository.get_by_hash(user_id, file_hash)
        doc_id = None
        chunk_count = 0
        page_count = 0
        
        if existing_doc and existing_doc.get("upload_status") == "ready":
            print(f"[INGEST] Document already exists and is READY in DB. ID: {existing_doc['id']}. Reusing.")
            doc_id = existing_doc["id"]
            page_count = existing_doc.get("page_count") or 0
            chunk_count = existing_doc.get("chunk_count") or 0
        else:
            # We must upload and ingest it
            if existing_doc:
                doc_id = existing_doc["id"]
                print(f"[INGEST] Document exists in DB with status '{existing_doc.get('upload_status')}', reprocessing ID: {doc_id}...")
            else:
                # Create row
                doc = await document_repository.create_document(
                    user_id=user_id,
                    original_filename=filename,
                    file_size=file_size,
                    file_hash=file_hash,
                    file_type="pdf"
                )
                doc_id = doc["id"]
                print(f"[INGEST] Created new document metadata row. ID: {doc_id}")
                
            # Upload to Supabase Storage
            storage_path = f"users/{user_id}/documents/{doc_id}/{doc_id}.pdf"
            print(f"[INGEST] Uploading to Supabase Storage bucket '{settings.SUPABASE_STORAGE_BUCKET}' at '{storage_path}'...")
            try:
                # Try to remove if it exists to avoid conflicts
                try:
                    supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([storage_path])
                except Exception:
                    pass
                
                supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                    path=storage_path,
                    file=file_bytes,
                    file_options={"content-type": "application/pdf"}
                )
                print("[INGEST] Storage upload successful.")
            except Exception as e:
                print(f"[INGEST] Storage upload failed: {e}")
                await document_repository.mark_failed(doc_id, f"Storage upload error: {str(e)}")
                sys.exit(1)
                
            # Update storage path
            await document_repository.update_storage_path(
                document_id=doc_id,
                storage_path=storage_path,
                upload_status="stored"
            )
            
            # Execute Ingestion Pipeline
            print(f"[INGEST] Triggering ingestion pipeline for document: {doc_id}...")
            try:
                await run_document_ingestion(doc_id)
            except Exception as e:
                print(f"[INGEST] Ingestion pipeline failed: {e}")
                sys.exit(1)
                
            # Fetch completed details
            completed_doc = await document_repository.get_by_id(doc_id)
            if not completed_doc or completed_doc.get("upload_status") != "ready":
                print(f"[INGEST] ERROR: Document ingestion finished but status is '{completed_doc.get('upload_status') if completed_doc else 'None'}' instead of 'ready'.")
                sys.exit(1)
                
            page_count = completed_doc.get("page_count") or 0
            chunk_count = completed_doc.get("chunk_count") or 0
            print(f"[INGEST] Document {doc_id} is READY. Pages: {page_count}, Chunks: {chunk_count}")
            
        manifest_data[filename] = {
            "filename": filename,
            "relative_path": f"evaluation/documents/{filename}",
            "file_hash": file_hash,
            "page_count": page_count,
            "language": language,
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            "document_id": doc_id,
            "chunk_count": chunk_count
        }
        
    # Write manifest
    manifest_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets"))
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "document_manifest.json")
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n[INGEST] Ingestion and manifest creation complete! Manifest saved to: {manifest_path}")

if __name__ == "__main__":
    asyncio.run(ingest_documents())
