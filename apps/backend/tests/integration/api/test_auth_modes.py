import pytest
import uuid
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.core.config import settings, Settings

client = TestClient(app)

# Helper UUIDs for testing
MOCK_USER = "c9d079ce-1858-437f-a168-99a85d28218b"
ALT_USER = "25890a31-7ae2-4a6a-b0fc-b275553e9c8b"

@pytest.fixture
def override_settings():
    """Fixture to backup and restore setting configurations after each test."""
    original_auth_mode = settings.AUTH_MODE
    original_mock_user_id = settings.MOCK_USER_ID
    original_app_env = settings.APP_ENV
    yield settings
    settings.AUTH_MODE = original_auth_mode
    settings.MOCK_USER_ID = original_mock_user_id
    settings.APP_ENV = original_app_env

@pytest.fixture
def mock_document_service():
    with patch("app.api.v1.documents.upload_and_ingest_document", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = {
            "document_id": "doc-123",
            "status": "ready",
            "is_duplicate": False
        }
        yield mock_upload

@pytest.fixture
def mock_document_repo():
    with patch("app.api.v1.documents.document_repository", new_callable=MagicMock) as mock_repo:
        yield mock_repo

@pytest.fixture
def mock_orchestrator():
    with patch("app.api.v1.ai.ai_orchestrator_service.execute_query", new_callable=AsyncMock) as mock_exec:
        from app.schemas.ai_schema import AIResponse, ExecutionMode
        mock_exec.return_value = AIResponse(
            status="success",
            message="Mocked AI Output",
            execution_mode=ExecutionMode.SINGLE,
            tasks=[],
            citations=[],
            confidence=0.95
        )
        yield mock_exec

@pytest.fixture
def mock_supabase_client():
    with patch("app.db.supabase_client.get_supabase_client") as mock_get_client, \
         patch("app.core.auth.get_supabase_client", create=True) as mock_auth_get_client:
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_client.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.in_.return_value = mock_query
        mock_query.insert.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        
        mock_get_client.return_value = mock_client
        mock_auth_get_client.return_value = mock_client
        yield mock_client, mock_query

# ──────────────────────────────────────────────────────────────────────────────
# 1. SETTINGS & SAFEGUARDS TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_settings_missing_mock_user_id_error():
    """Fails validation if AUTH_MODE=mock and MOCK_USER_ID is missing."""
    with pytest.raises(ValueError) as excinfo:
        Settings(AUTH_MODE="mock", MOCK_USER_ID="", APP_ENV="development").validate_auth_settings()
    assert "MOCK_USER_ID is required" in str(excinfo.value)

def test_settings_invalid_mock_user_id_error():
    """Fails validation if MOCK_USER_ID is not a valid UUID."""
    with pytest.raises(ValueError) as excinfo:
        Settings(AUTH_MODE="mock", MOCK_USER_ID="invalid-uuid-format", APP_ENV="development").validate_auth_settings()
    assert "is not a valid UUID" in str(excinfo.value)

def test_settings_production_mock_guard():
    """Fails validation if APP_ENV=production and AUTH_MODE=mock."""
    with pytest.raises(ValueError) as excinfo:
        Settings(AUTH_MODE="mock", MOCK_USER_ID=MOCK_USER, APP_ENV="production").validate_auth_settings()
    assert "AUTH_MODE cannot be set to 'mock' in production" in str(excinfo.value)

# ──────────────────────────────────────────────────────────────────────────────
# 2. MOCK MODE TESTS (without Auth Header)
# ──────────────────────────────────────────────────────────────────────────────

def test_mock_mode_pdf_upload_success(override_settings, mock_document_service):
    """Verifies document upload succeeds in mock mode without Authorization header."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    valid_pdf_content = b"%PDF-1.4\n%...\n1 0 obj\n..."
    files = {"file": ("test.pdf", valid_pdf_content, "application/pdf")}
    
    response = client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["document_id"] == "doc-123"
    
    # Assert that stored record will use MOCK_USER
    mock_document_service.assert_called_once()
    assert mock_document_service.call_args[0][0] == MOCK_USER

def test_mock_mode_get_document_status_success(override_settings, mock_document_repo):
    """Verifies document status query succeeds in mock mode without Auth header."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    mock_document_repo.get_by_id = AsyncMock(return_value={
        "id": "doc-123",
        "user_id": MOCK_USER,
        "upload_status": "ready",
        "page_count": 5,
        "chunk_count": 10
    })

    response = client.get("/api/v1/documents/doc-123/status")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ready"

def test_mock_mode_chat_success(override_settings, mock_orchestrator):
    """Verifies chat endpoint succeeds in mock mode without Auth header."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    payload = {
        "session_id": "session-abc",
        "message": "Explain quantum computing",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-123/chat", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Mocked AI Output"
    
    # Verify mock user ID was injected internally
    mock_orchestrator.assert_called_once()
    called_request = mock_orchestrator.call_args[1]["request"]
    assert called_request.user_id == MOCK_USER

def test_mock_mode_summary_success(override_settings, mock_orchestrator):
    """Verifies summary endpoint succeeds in mock mode without Auth header."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    payload = {
        "session_id": "session-abc",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/doc-123/summary", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Mocked AI Output"

    # Verify mock user ID was injected internally
    mock_orchestrator.assert_called_once()
    called_request = mock_orchestrator.call_args[1]["request"]
    assert called_request.user_id == MOCK_USER

def test_mock_mode_quiz_generation_success(override_settings, mock_orchestrator):
    """Verifies quiz generation succeeds in mock mode without Auth header."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    payload = {
        "session_id": "session-abc",
        "language": "en",
        "difficulty": "medium",
        "number_of_questions": 5
    }

    response = client.post("/api/v1/documents/doc-123/quiz", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Mocked AI Output"

    # Verify mock user ID was injected internally
    mock_orchestrator.assert_called_once()
    called_request = mock_orchestrator.call_args[1]["request"]
    assert called_request.user_id == MOCK_USER

def test_mock_mode_quiz_submission_success(override_settings, mock_supabase_client):
    """Verifies quiz submission succeeds in mock mode without Auth header."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    mock_client, mock_query = mock_supabase_client

    # Define custom query mock execution for quiz submission
    def execute_side_effect():
        call_args = mock_client.table.call_args_list
        target_table = call_args[-1][0][0]
        
        if target_table == "quizzes":
            return MagicMock(data=[{
                "id": "quiz-123",
                "user_id": MOCK_USER,
                "document_id": "doc-123",
                "title": "Mock Quiz"
            }])
        elif target_table == "quiz_attempts":
            # Return empty for idempotency check
            return MagicMock(data=[])
        elif target_table == "quiz_questions":
            return MagicMock(data=[{
                "id": "q-1",
                "quiz_id": "quiz-123",
                "question_text": "Q1?",
                "options": ["A", "B", "C", "D"]
            }])
        elif target_table == "quiz_question_answers":
            return MagicMock(data=[{
                "question_id": "q-1",
                "correct_option_id": 0,
                "explanation": "Correct answer is A"
            }])
        return MagicMock(data=[])

    mock_query.execute.side_effect = execute_side_effect

    payload = {
        "attempt_number": 1,
        "idempotency_key": "idemp-key-1",
        "responses": [
            {"question_id": "q-1", "selected_option_id": 0}
        ]
    }

    response = client.post("/api/v1/documents/quizzes/quiz-123/submit", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "completed"
    assert response.json()["score_percentage"] == 100.0

def test_mock_mode_client_supplied_user_id_ignored(override_settings, mock_orchestrator):
    """Verifies that client-supplied user_id in payloads is ignored and overridden by MOCK_USER_ID."""
    override_settings.AUTH_MODE = "mock"
    override_settings.MOCK_USER_ID = MOCK_USER

    # Client tries to pass a foreign user_id
    payload = {
        "user_id": ALT_USER,
        "session_id": "session-abc",
        "message": "Help me",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-123/chat", json=payload)
    assert response.status_code == status.HTTP_200_OK
    
    # Assert orchestrator received the backend's MOCK_USER, not the ALT_USER passed by client
    mock_orchestrator.assert_called_once()
    called_request = mock_orchestrator.call_args[1]["request"]
    assert called_request.user_id == MOCK_USER

# ──────────────────────────────────────────────────────────────────────────────
# 3. SUPABASE MODE TESTS
# ──────────────────────────────────────────────────────────────────────────────

def test_supabase_mode_missing_token_returns_401(override_settings):
    """Verifies that missing token returns 401 Unauthorized in supabase mode."""
    override_settings.AUTH_MODE = "supabase"

    response = client.get("/api/v1/documents/doc-123/status")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "credentials were not provided" in response.json()["detail"]

def test_supabase_mode_invalid_token_returns_401(override_settings, mock_supabase_client):
    """Verifies that invalid token returns 401 Unauthorized in supabase mode."""
    override_settings.AUTH_MODE = "supabase"
    mock_client, _ = mock_supabase_client

    # Mock supabase auth to raise an exception for invalid token
    mock_client.auth.get_user.side_effect = Exception("Invalid token signature")

    headers = {"Authorization": "Bearer invalid-jwt-token"}
    response = client.get("/api/v1/documents/doc-123/status", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or expired authentication token" in response.json()["detail"]

def test_supabase_mode_valid_token_resolves_user(override_settings, mock_supabase_client, mock_document_repo):
    """Verifies that a valid token resolves the user UUID in supabase mode."""
    override_settings.AUTH_MODE = "supabase"
    mock_client, _ = mock_supabase_client

    # Mock valid supabase token resolving to ALT_USER
    mock_user_resp = MagicMock()
    mock_user_resp.user.id = ALT_USER
    mock_client.auth.get_user.return_value = mock_user_resp

    mock_document_repo.get_by_id = AsyncMock(return_value={
        "id": "doc-123",
        "user_id": ALT_USER,
        "upload_status": "ready"
    })

    headers = {"Authorization": f"Bearer valid-jwt-token"}
    response = client.get("/api/v1/documents/doc-123/status", headers=headers)
    assert response.status_code == status.HTTP_200_OK

def test_supabase_mode_cross_user_document_access_blocked(override_settings, mock_supabase_client, mock_document_repo):
    """Verifies cross-user document status access is blocked in supabase mode."""
    override_settings.AUTH_MODE = "supabase"
    mock_client, _ = mock_supabase_client

    # Authenticate as ALT_USER
    mock_user_resp = MagicMock()
    mock_user_resp.user.id = ALT_USER
    mock_client.auth.get_user.return_value = mock_user_resp

    # Document belongs to MOCK_USER
    mock_document_repo.get_by_id = AsyncMock(return_value={
        "id": "doc-123",
        "user_id": MOCK_USER,
        "upload_status": "ready"
    })

    headers = {"Authorization": f"Bearer valid-jwt-token"}
    response = client.get("/api/v1/documents/doc-123/status", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Permission denied" in response.json()["detail"]

def test_supabase_mode_cross_user_quiz_access_blocked(override_settings, mock_supabase_client):
    """Verifies cross-user quiz access/submission is blocked in supabase mode."""
    override_settings.AUTH_MODE = "supabase"
    mock_client, mock_query = mock_supabase_client

    # Authenticate as ALT_USER
    mock_user_resp = MagicMock()
    mock_user_resp.user.id = ALT_USER
    mock_client.auth.get_user.return_value = mock_user_resp

    # Quiz belongs to MOCK_USER
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{
        "id": "quiz-123",
        "user_id": MOCK_USER,
        "document_id": "doc-123"
    }])

    headers = {"Authorization": f"Bearer valid-jwt-token"}
    payload = {
        "attempt_number": 1,
        "idempotency_key": "idemp-key-1",
        "responses": []
    }
    response = client.post("/api/v1/documents/quizzes/quiz-123/submit", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Permission denied" in response.json()["detail"]
