from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

# Standard mock document details
MOCK_USER = "00000000-0000-0000-0000-000000000000"
MOCK_READY_DOC = {
    "id": "doc-ready-123",
    "user_id": MOCK_USER,
    "upload_status": "ready",
    "chunk_count": 5
}
MOCK_NOT_READY_DOC = {
    "id": "doc-not-ready",
    "user_id": MOCK_USER,
    "upload_status": "uploaded",
    "chunk_count": 0
}
MOCK_FOREIGN_DOC = {
    "id": "doc-foreign",
    "user_id": "11111111-1111-1111-1111-111111111111",
    "upload_status": "ready",
    "chunk_count": 5
}

@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_success(mock_repo):
    """Verifies successful grounding chat with clean output format."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "message": "لخصلي الملف واعمل quiz",
        "language": "ar",
        "user_level": "intermediate",
        "request_source": "chat"
    }

    response = client.post("/api/v1/documents/doc-ready-123/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Summary" in data["message"]
    assert "Quiz" in data["message"]
    assert len(data["tasks"]) == 2
    assert data["confidence"] == 0.5


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_document_not_ready(mock_repo):
    """Verifies that un-indexed documents are rejected by Document Guard."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_NOT_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "message": "Explain this to me",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-not-ready/chat", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "DOCUMENT_NOT_READY"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_access_denied(mock_repo):
    """Verifies ownership check fails when document is owned by a different user."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_FOREIGN_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "message": "Explain this to me",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-foreign/chat", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "DOCUMENT_ACCESS_DENIED"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_document_not_found(mock_repo):
    """Verifies check fails when document_id is not in DB."""
    mock_repo.get_by_id = AsyncMock(return_value=None)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "message": "Explain this to me",
        "language": "en"
    }

    response = client.post("/api/v1/documents/invalid-id/chat", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "DOCUMENT_NOT_FOUND"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_vague_clarification(mock_repo):
    """Verifies vague prompts trigger clarification rather than vector QA execution."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "message": "hi",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-ready-123/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_clarification"
    assert "How can I help" in data["message"]
    assert len(data["tasks"]) == 0


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_summary_shortcut_success(mock_repo):
    """Verifies the summary shortcut endpoint execution."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "language": "en",
        "user_level": "beginner",
        "summary_style": "bullet_points"
    }

    response = client.post("/api/v1/documents/doc-ready-123/summary", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Document Comprehensive Summary" in data["message"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["type"] == "summary"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_quiz_shortcut_success(mock_repo):
    """Verifies the quiz shortcut endpoint execution."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "sess-xyz",
        "language": "en",
        "user_level": "intermediate",
        "difficulty": "medium",
        "number_of_questions": 5,
        "question_type": "multiple_choice"
    }

    response = client.post("/api/v1/documents/doc-ready-123/quiz", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Simulated Quiz" in data["message"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["type"] == "quiz"
