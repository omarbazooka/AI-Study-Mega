from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.db.repositories.chunk_repository.get_chunks_by_document")
def test_memory_contains_context_but_rag_returns_zero_chunks(mock_chunks, mock_doc):
    """
    Critical Integration Test:
    Even if memory contains history, if RAG returns zero chunks,
    the response must fall back to the grounding fallback text:
    "لم أجد إجابة واضحة في الملف المرفوع."
    """
    mock_doc.return_value = {
        "id": "doc-empty-rag",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    # Simulate RAG retrieval returning zero chunks
    mock_chunks.return_value = []

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test-empty",
        "message": "What did I study about mitosis last time?",
        "language": "ar",
        "user_level": "intermediate",
        "request_source": "chat"
    }

    response = client.post("/api/v1/documents/doc-empty-rag/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_answer"
    assert data["message"] == "لم أجد إجابة واضحة في الملف المرفوع."
