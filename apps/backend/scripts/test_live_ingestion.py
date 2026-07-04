import sys
import os
import asyncio
import hashlib

# Add backend directory absolutely
sys.path.append(r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend")

from app.db.supabase_client import get_supabase_client
from app.core.config import settings
from app.db.repositories import document_repository, chunk_repository
from app.ai_system.ingestion.ingestion_pipeline import process_document

# Simple PDF generator using reportlab to create a real, parseable PDF file
# Since reportlab is in the pip list (we saw it!), we can generate a real PDF!
from reportlab.pdfgen import canvas

def create_sample_pdf(filename: str) -> bytes:
    """
    Creates a simple multi-page PDF document for testing.
    """
    buffer = os.path.join(os.path.dirname(__file__), filename)
    c = canvas.Canvas(buffer)
    
    # Page 1
    c.drawString(100, 750, "AI Study Platform for All Learners")
    c.drawString(100, 720, "Project Proposal Details")
    c.drawString(100, 680, "Project Definition:")
    c.drawString(100, 660, "This is paragraph one of the project definition. It is designed to test")
    c.drawString(100, 640, "our parser, cleaner, chunker, and embedding generator end-to-end.")
    c.drawString(100, 620, "We want to ensure that paragraphs are kept together and overlap works.")
    
    c.drawString(100, 560, "Project Goals:")
    c.drawString(100, 540, "1- Build a document-aware chatbot capable of answering questions.")
    c.drawString(100, 520, "2- Build an automatic summarization tool for document summaries.")
    c.showPage()
    
    # Page 2
    c.drawString(100, 750, "Methodology and Technologies")
    c.drawString(100, 720, "We use Next.js for frontend and FastAPI for backend development.")
    c.drawString(100, 700, "Supabase serves as the backend database storing text chunks and vectors.")
    c.drawString(100, 680, "The embedding model we load is all-MiniLM-L6-v2 returning 384 dimensions.")
    c.showPage()
    
    c.save()
    
    with open(buffer, "rb") as f:
        pdf_bytes = f.read()
        
    # Clean up local file
    try:
        os.remove(buffer)
    except:
        pass
        
    return pdf_bytes

async def test_pipeline():
    print("=" * 60)
    print("          LIVE PIPELINE END-TO-END INGESTION TEST")
    print("=" * 60)
    
    user_id = "00000000-0000-0000-0000-000000000000"
    filename = "live_test_sample.pdf"
    
    print("[1/6] Generating sample PDF content...")
    pdf_bytes = create_sample_pdf(filename)
    file_size = len(pdf_bytes)
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    print(f" -> Generated PDF size: {file_size} bytes. Hash: {file_hash}")
    
    print("\n[2/6] Checking for duplicates or existing records...")
    # Clean up previous test run if any to allow re-run
    existing = await document_repository.get_by_hash(user_id, file_hash)
    if existing:
        print(f" -> Found previous run document ID: {existing['id']}. Deleting chunks and record...")
        await chunk_repository.delete_chunks_by_document(existing["id"])
        supabase = get_supabase_client()
        if existing.get("storage_path"):
            try:
                supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove(existing["storage_path"])
            except:
                pass
        supabase.table("documents").delete().eq("id", existing["id"]).execute()
        print(" -> Previous record cleaned up.")
        
    print("\n[3/6] Creating document row in database...")
    doc = await document_repository.create_document(
        user_id=user_id,
        original_filename=filename,
        file_size=file_size,
        file_hash=file_hash
    )
    doc_id = doc["id"]
    print(f" -> SUCCESS: Created document row with ID: {doc_id} and status: {doc['upload_status']}")
    
    print("\n[4/6] Uploading raw PDF to Supabase Storage...")
    storage_path = f"users/{user_id}/documents/{doc_id}/{doc_id}.pdf"
    supabase = get_supabase_client()
    try:
        supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf"}
        )
        print(f" -> SUCCESS: Uploaded to bucket '{settings.SUPABASE_STORAGE_BUCKET}' at: {storage_path}")
    except Exception as e:
        print(f" -> FAILURE: Upload to storage failed: {e}")
        await document_repository.mark_failed(doc_id, str(e))
        return
        
    print("\n[5/6] Updating document metadata with storage path...")
    await document_repository.update_storage_path(
        document_id=doc_id,
        storage_path=storage_path,
        upload_status="stored"
    )
    print(" -> Storage path updated in database.")
    
    print("\n[6/6] Executing background Ingestion Pipeline...")
    print(" -> This will parse, clean, chunk, generate embeddings (all-MiniLM-L6-v2), and insert into pgvector...")
    try:
        await process_document(doc_id)
        
        # Verify final document status
        final_doc = await document_repository.get_by_id(doc_id)
        print("\n" + "=" * 60)
        print("                 INGESTION COMPLETE SUMMARY")
        print("=" * 60)
        print(f"Document ID   : {final_doc['id']}")
        print(f"Final Status  : {final_doc['upload_status']}")
        print(f"Page Count    : {final_doc['page_count']}")
        print(f"Chunk Count   : {final_doc['chunk_count']}")
        print(f"Error Message : {final_doc.get('error_message')}")
        
        # Fetch chunk details from DB
        chunks = await chunk_repository.get_chunks_by_document(doc_id)
        print(f"\nSaved Chunks in Database (Count: {len(chunks)}):")
        for chunk in chunks:
            vector_preview = str(chunk['embedding'])[:60] + "..." if chunk.get('embedding') else "None"
            print(f" - Chunk {chunk['chunk_index']} (Page {chunk['page_start']}-{chunk['page_end']}):")
            print(f"   Content preview: {chunk['content'][:80].replace(chr(10), ' ')}...")
            print(f"   Vector Preview : {vector_preview}")
            
        if final_doc['upload_status'] == "ready" and len(chunks) > 0:
            print("\n>>> PIPELINE TEST PASSED SUCCESSFULLY IN LIVE ENVIRONMENT! <<<")
        else:
            print("\n>>> PIPELINE TEST FAILED! <<<")
            
    except Exception as e:
        print(f" -> Error during pipeline execution: {e}")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
