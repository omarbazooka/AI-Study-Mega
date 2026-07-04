from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

client = TestClient(app)

@patch("app.services.document_service.document_repository")
@patch("app.services.document_service.get_supabase_client")
@patch("app.services.document_service.run_document_ingestion")
def test_upload_document_success(mock_worker, mock_supabase, mock_repo):
    """
    Integration test verifying that a valid PDF upload initiates the pipeline
    and registers a background worker task.
    """
    # 1. Mock DB repository responses
    mock_repo.get_by_hash = AsyncMock(return_value=None)
    mock_repo.create_document = AsyncMock(return_value={
        "id": "doc-uuid-123",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "original_filename": "lecture1.pdf",
        "upload_status": "uploaded"
    })
    mock_repo.update_storage_path = AsyncMock(return_value={
        "id": "doc-uuid-123",
        "upload_status": "stored"
    })

    # 2. Mock Supabase Storage operations
    mock_storage_bucket = MagicMock()
    mock_supabase_client = MagicMock()
    mock_supabase.return_value = mock_supabase_client
    mock_supabase_client.storage.from_ = MagicMock(return_value=mock_storage_bucket)
    mock_storage_bucket.upload = MagicMock(return_value=None)

    # 3. Simulate file upload with valid PDF contents
    valid_pdf_content = b"%PDF-1.4\n%...\n1 0 obj\n..."
    files = {"file": ("lecture1.pdf", valid_pdf_content, "application/pdf")}
    
    response = client.post("/api/v1/documents/upload", files=files)
    
    assert response.status_code == 202
    data = response.json()
    assert data["document_id"] == "doc-uuid-123"
    assert data["status"] == "processing"
    assert "uploaded successfully" in data["message"]
    
    # 4. Assert that background worker task was registered
    mock_worker.assert_called_once_with("doc-uuid-123")

@patch("app.services.document_service.document_repository")
def test_upload_duplicate_document(mock_repo):
    """
    Integration test verifying that uploading an identical file (same hash and user)
    aborts upload and returns the existing document details immediately.
    """
    # Mock that a document with identical hash already exists in DB
    mock_repo.get_by_hash = AsyncMock(return_value={
        "id": "existing-doc-uuid",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready"
    })

    valid_pdf_content = b"%PDF-1.4\n%...\n1 0 obj\n..."
    files = {"file": ("duplicate.pdf", valid_pdf_content, "application/pdf")}
    
    response = client.post("/api/v1/documents/upload", files=files)
    
    assert response.status_code == 202
    data = response.json()
    assert data["document_id"] == "existing-doc-uuid"
    assert data["status"] == "ready"
    assert "already uploaded" in data["message"]

@patch("app.api.v1.documents.document_repository")
def test_get_document_status_success(mock_repo):
    """
    Integration test checking that the status query returns correct metadata and stage.
    """
    mock_repo.get_by_id = AsyncMock(return_value={
        "id": "doc-uuid-123",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "page_count": 12,
        "chunk_count": 45,
        "error_message": None
    })

    response = client.get("/api/v1/documents/doc-uuid-123/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == "doc-uuid-123"
    assert data["status"] == "ready"
    assert data["page_count"] == 12
    assert data["chunk_count"] == 45
    assert data["error_message"] is None

@patch("app.api.v1.documents.document_repository")
def test_get_document_status_not_found(mock_repo):
    """
    Integration test checking error response when status is queried for a non-existent document ID.
    """
    mock_repo.get_by_id = AsyncMock(return_value=None)

    response = client.get("/api/v1/documents/invalid-uuid/status")
    
    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]
