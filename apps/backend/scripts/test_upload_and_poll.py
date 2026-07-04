import sys
import os
import io
import time

# Add backend directory absolutely
sys.path.append(r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend")

from fastapi.testclient import TestClient
from app.main import app
from reportlab.pdfgen import canvas
from app.db.repositories import chunk_repository

def create_temp_pdf() -> bytes:
    """
    Creates a simple 3-page PDF document for live API testing.
    """
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer)
    
    # Page 1
    c.drawString(100, 750, "Study Guide: Quantum Mechanics")
    c.drawString(100, 720, "Introduction to quantum operators and states.")
    c.drawString(100, 680, "A wave function describes the quantum state of a isolated system.")
    c.showPage()
    
    # Page 2
    c.drawString(100, 750, "Section 1: The Schrodinger Equation")
    c.drawString(100, 720, "H psi = E psi represents the time-independent equation.")
    c.showPage()
    
    # Page 3
    c.drawString(100, 750, "Section 2: Operators and Observables")
    c.drawString(100, 720, "Hermitian operators represent observable physical quantities.")
    c.showPage()
    
    c.save()
    return pdf_buffer.getvalue()

def run_upload_and_poll():
    print("=" * 60)
    print("          API LIVE INGESTION FLOW AND POLLING TEST")
    print("=" * 60)
    
    client = TestClient(app)
    pdf_bytes = create_temp_pdf()
    files = {"file": ("quantum_guide.pdf", pdf_bytes, "application/pdf")}
    
    # Step 1: Upload via API
    print("[1/3] Uploading PDF via POST /api/v1/documents/upload...")
    response = client.post("/api/v1/documents/upload", files=files)
    if response.status_code != 202:
        print(f" -> FAILURE: Upload returned status {response.status_code}")
        print(f"    Body: {response.text}")
        sys.exit(1)
        
    data = response.json()
    doc_id = data["document_id"]
    print(f" -> SUCCESS: Document uploaded. ID: {doc_id}. Initial status: {data['status']}")
    
    # Step 2: Poll GET status endpoint
    print("\n[2/3] Polling GET /api/v1/documents/{id}/status for transitions...")
    max_attempts = 20
    poll_interval = 2.0
    last_status = None
    
    for attempt in range(max_attempts):
        status_res = client.get(f"/api/v1/documents/{doc_id}/status")
        if status_res.status_code != 200:
            print(f" -> ERROR: Status endpoint returned {status_res.status_code}")
            sys.exit(1)
            
        status_data = status_res.json()
        current_status = status_data["status"]
        
        # Print status when it changes
        if current_status != last_status:
            print(f" -> Status transitioned to: {current_status.upper()}")
            last_status = current_status
            
        if current_status == "ready":
            print(f"\n -> SUCCESS: Ingestion pipeline reached READY status!")
            print(f"    Page Count : {status_data.get('page_count')}")
            print(f"    Chunk Count: {status_data.get('chunk_count')}")
            break
        elif current_status == "failed":
            print(f"\n -> FAILURE: Ingestion pipeline failed.")
            print(f"    Reason: {status_data.get('error_message')}")
            sys.exit(1)
            
        time.sleep(poll_interval)
    else:
        print(f"\n -> TIMEOUT: Document ingestion did not complete within {max_attempts * poll_interval}s.")
        sys.exit(1)
        
    # Step 3: Verify chunks are in VectorDB
    print("\n[3/3] Verifying chunks were inserted into pgvector...")
    chunks = chunk_repository.supabase.table("document_chunks").select("id, content").eq("document_id", doc_id).execute().data
    print(f" -> Found {len(chunks)} chunks saved in PostgreSQL + pgvector.")
    if len(chunks) > 0:
         print(f" -> Content preview of first chunk: {chunks[0]['content'][:100]}...")
         print("\n>>> LIVE API UPLOAD AND POLLING VERIFICATION PASSED! <<<")
    else:
         print("\n>>> LIVE API UPLOAD AND POLLING VERIFICATION FAILED! <<<")
         sys.exit(1)

if __name__ == "__main__":
    run_upload_and_poll()
