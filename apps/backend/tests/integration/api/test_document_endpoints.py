import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.schemas.ai_schema import AIResponse, TaskResult

client = TestClient(app)

MOCK_USER = "00000000-0000-0000-0000-000000000000"
MOCK_FOREIGN_USER = "11111111-1111-1111-1111-111111111111"

@pytest.fixture
def mock_supabase_client():
    with patch("app.db.repositories.document_repository.supabase") as mock_repo_supabase, \
         patch("app.db.repositories.chat_repository.supabase") as mock_chat_supabase, \
         patch("app.api.v1.sessions.chat_repository") as mock_api_chat_repo:
        
        yield {
            "document_db": mock_repo_supabase,
            "chat_db": mock_chat_supabase,
            "api_chat_repo": mock_api_chat_repo
        }

@pytest.fixture
def mock_auth():
    with patch("app.core.auth.get_current_user", return_value=MOCK_USER):
        yield

# ──────────────────────────────────────────────────────────────────────
# 1. GET /api/v1/documents tests
# ──────────────────────────────────────────────────────────────────────

@patch("app.db.repositories.document_repository.get_all_by_user_id", new_callable=AsyncMock)
def test_list_documents_success(mock_get_all, mock_auth):
    """Verifies listing documents successfully for authenticated user."""
    mock_get_all.return_value = [
        {
            "id": "doc-2",
            "original_filename": "anatomy.pdf",
            "upload_status": "ready",
            "page_count": 10,
            "chunk_count": 40,
            "error_message": None,
            "created_at": "2026-07-11T02:00:00Z",
            "updated_at": "2026-07-11T02:05:00Z"
        },
        {
            "id": "doc-1",
            "original_filename": "biology.pdf",
            "upload_status": "failed",
            "page_count": 0,
            "chunk_count": 0,
            "error_message": "Chunking error",
            "created_at": "2026-07-11T01:00:00Z",
            "updated_at": "2026-07-11T01:05:00Z"
        }
    ]
    
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "doc-2"
    assert data["items"][1]["id"] == "doc-1"
    mock_get_all.assert_called_once_with(MOCK_USER)

@patch("app.db.repositories.document_repository.get_all_by_user_id", new_callable=AsyncMock)
def test_list_documents_empty(mock_get_all, mock_auth):
    """Verifies listing returns empty array when user has no documents."""
    mock_get_all.return_value = []
    
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []

# ──────────────────────────────────────────────────────────────────────
# 2. POST /api/v1/documents/{document_id}/reprocess tests
# ──────────────────────────────────────────────────────────────────────

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
def test_reprocess_not_found(mock_get_by_id, mock_auth):
    """Reprocess returns 404 if document does not exist."""
    mock_get_by_id.return_value = None
    response = client.post("/api/v1/documents/invalid-doc/reprocess")
    assert response.status_code == 404
    assert response.json()["detail"] == "DOCUMENT_NOT_FOUND"

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
def test_reprocess_wrong_owner(mock_get_by_id, mock_auth):
    """Reprocess returns 403 if user does not own the document."""
    mock_get_by_id.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_FOREIGN_USER,
        "upload_status": "failed"
    }
    response = client.post("/api/v1/documents/doc-xyz/reprocess")
    assert response.status_code == 403
    assert response.json()["detail"] == "DOCUMENT_ACCESS_DENIED"

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
def test_reprocess_ready_rejected(mock_get_by_id, mock_auth):
    """Reprocess returns 400 if document is already ready."""
    mock_get_by_id.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "ready"
    }
    response = client.post("/api/v1/documents/doc-xyz/reprocess")
    assert response.status_code == 400
    assert response.json()["detail"] == "READY_CANNOT_BE_RETRIED"

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
def test_reprocess_processing_rejected(mock_get_by_id, mock_auth):
    """Reprocess returns 409 if document is currently parsing/embedding."""
    mock_get_by_id.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "parsing"
    }
    response = client.post("/api/v1/documents/doc-xyz/reprocess")
    assert response.status_code == 409
    assert response.json()["detail"] == "PROCESSING_OR_RETRY_ACTIVE"

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.atomic_update_status_reprocess", new_callable=AsyncMock)
@patch("app.db.repositories.chunk_repository.delete_chunks_by_document", new_callable=AsyncMock)
@patch("app.api.v1.documents.BackgroundTasks.add_task")
def test_reprocess_success(mock_add_task, mock_delete_chunks, mock_atomic, mock_get_by_id, mock_auth):
    """Reprocess successfully resets failed document metadata, chunks, and dispatches worker."""
    mock_get_by_id.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "failed"
    }
    mock_atomic.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "stored"
    }
    
    with patch("app.db.supabase_client.get_supabase_client") as mock_supabase_getter:
        mock_supabase = MagicMock()
        mock_supabase_getter.return_value = mock_supabase
        mock_supabase.table.return_value = mock_supabase
        mock_supabase.delete.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.execute.return_value = MagicMock(data=[])
        
        response = client.post("/api/v1/documents/doc-xyz/reprocess")
        
        assert response.status_code == 202
        assert response.json()["status"] == "processing"
        mock_delete_chunks.assert_called_once_with("doc-xyz")
        mock_atomic.assert_called_once_with("doc-xyz", MOCK_USER)
        mock_add_task.assert_called_once()

# ──────────────────────────────────────────────────────────────────────
# 3. POST /api/v1/documents/{document_id}/sessions tests
# ──────────────────────────────────────────────────────────────────────

@patch("app.services.session_service.document_repository.get_by_id", new_callable=AsyncMock)
@patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock)
@patch("app.services.session_service.chat_repository.create_chat_session", new_callable=AsyncMock)
def test_create_session_success(mock_create_session, mock_get_session, mock_get_doc, mock_auth):
    """Verifies session creation scopes to the user and document successfully."""
    mock_get_doc.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER
    }
    mock_get_session.return_value = None
    mock_create_session.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "user_id": MOCK_USER,
        "document_id": "doc-xyz",
        "created_at": "2026-07-11T03:00:00Z",
        "updated_at": "2026-07-11T03:00:00Z"
    }
    
    response = client.post("/api/v1/documents/doc-xyz/sessions")
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "00000000-0000-0000-0000-000000000001"
    assert data["document_id"] == "doc-xyz"

@patch("app.services.session_service.document_repository.get_by_id", new_callable=AsyncMock)
def test_create_session_doc_access_denied(mock_get_doc, mock_auth):
    """Create session fails if user doesn't own document."""
    mock_get_doc.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_FOREIGN_USER
    }
    response = client.post("/api/v1/documents/doc-xyz/sessions")
    assert response.status_code == 403
    assert response.json()["detail"] == "DOCUMENT_ACCESS_DENIED"

# ──────────────────────────────────────────────────────────────────────
# 4. GET /api/v1/documents/{document_id}/sessions/{session_id}/messages tests
# ──────────────────────────────────────────────────────────────────────

@patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock)
def test_get_history_not_found(mock_get_session, mock_auth):
    """History returns 404 if session does not exist."""
    mock_get_session.return_value = None
    response = client.get("/api/v1/documents/doc-xyz/sessions/00000000-0000-0000-0000-000000000001/messages")
    assert response.status_code == 404
    assert response.json()["detail"] == "SESSION_NOT_FOUND"

@patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock)
def test_get_history_access_denied(mock_get_session, mock_auth):
    """History returns 403 if session belongs to foreign user."""
    mock_get_session.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "user_id": MOCK_FOREIGN_USER,
        "document_id": "doc-xyz"
    }
    response = client.get("/api/v1/documents/doc-xyz/sessions/00000000-0000-0000-0000-000000000001/messages")
    assert response.status_code == 403
    assert response.json()["detail"] == "SESSION_ACCESS_DENIED"

@patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock)
def test_get_history_legacy_rejected(mock_get_session, mock_auth):
    """History returns 400 if session is legacy NULL document session."""
    mock_get_session.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "user_id": MOCK_USER,
        "document_id": None
    }
    response = client.get("/api/v1/documents/doc-xyz/sessions/00000000-0000-0000-0000-000000000001/messages")
    assert response.status_code == 400
    assert response.json()["detail"] == "LEGACY_SESSION_REJECTED"

@patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock)
def test_get_history_mismatch(mock_get_session, mock_auth):
    """History returns 400 if session document binding differs from path."""
    mock_get_session.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "user_id": MOCK_USER,
        "document_id": "doc-other"
    }
    response = client.get("/api/v1/documents/doc-xyz/sessions/00000000-0000-0000-0000-000000000001/messages")
    assert response.status_code == 400
    assert response.json()["detail"] == "SESSION_DOCUMENT_MISMATCH"

# ──────────────────────────────────────────────────────────────────────
# 5. AI Session Cross-document and Quiz Metadata tests
# ──────────────────────────────────────────────────────────────────────

@patch("app.api.v1.ai.validate_session_ownership_and_document", new_callable=AsyncMock)
@patch("app.api.v1.ai.ai_orchestrator_service.execute_query", new_callable=AsyncMock)
def test_ai_quiz_response_metadata_quiz(mock_exec, mock_validate, mock_auth):
    """Verifies that generated quiz questions are nested inside response.metadata['quiz'] and conceal answers."""
    mock_validate.return_value = {}
    
    quiz_detail = {
        "quiz_id": "quiz-123",
        "title": "Photosynthesis Quiz",
        "questions": [
            {
                "id": "q-1",
                "question_text": "What is chlorophyll?",
                "options": ["A pigment", "A metal", "An organ", "A gas"],
                "difficulty": "easy",
                "concept": "plant cells"
            }
        ]
    }
    
    mock_exec.return_value = AIResponse(
        status="success",
        message="Photosynthesis Quiz content",
        execution_mode="single",
        tasks=[
            TaskResult(
                task_id="t-1",
                type="quiz",
                status="success",
                content="Photosynthesis Quiz content",
                confidence=0.95,
                metadata={"quiz": quiz_detail}
            )
        ],
        citations=[],
        confidence=0.95,
        metadata={"quiz": quiz_detail}
    )

    payload = {
        "session_id": "sess-xyz",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-xyz/quiz", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Assert quiz metadata fields
    assert "quiz" in data["metadata"]
    quiz = data["metadata"]["quiz"]
    assert quiz["quiz_id"] == "quiz-123"
    assert quiz["title"] == "Photosynthesis Quiz"
    assert len(quiz["questions"]) == 1
    
    question = quiz["questions"][0]
    assert question["id"] == "q-1"
    assert question["question_text"] == "What is chlorophyll?"
    assert len(question["options"]) == 4
    
    # Assert correct answer is hidden from metadata fields to prevent cheating
    assert "correct" not in question
    assert "correct_option_id" not in question
    assert "correct_answer" not in question

# ──────────────────────────────────────────────────────────────────────
# 6. Negative Quiz Schema validation tests
# ──────────────────────────────────────────────────────────────────────

from pydantic import ValidationError
import uuid
from app.schemas.ai_schema import QuizDetail, QuizQuestionPublic

def test_quiz_schema_three_options_rejected():
    """Verify that a question with only 3 options is rejected by schema validation."""
    with pytest.raises(ValidationError) as excinfo:
        QuizQuestionPublic(
            id=uuid.uuid4(),
            question_text="Sample question?",
            options=["Opt1", "Opt2", "Opt3"],  # 3 options
            difficulty="easy"
        )
    assert "List should have at least 4 items" in str(excinfo.value)

def test_quiz_schema_five_options_rejected():
    """Verify that a question with 5 options is rejected by schema validation."""
    with pytest.raises(ValidationError) as excinfo:
        QuizQuestionPublic(
            id=uuid.uuid4(),
            question_text="Sample question?",
            options=["Opt1", "Opt2", "Opt3", "Opt4", "Opt5"],  # 5 options
            difficulty="medium"
        )
    assert "List should have at most 4 items" in str(excinfo.value)

def test_quiz_schema_invalid_difficulty_rejected():
    """Verify that invalid difficulty values are rejected by schema validation."""
    with pytest.raises(ValidationError) as excinfo:
        QuizQuestionPublic(
            id=uuid.uuid4(),
            question_text="Sample question?",
            options=["Opt1", "Opt2", "Opt3", "Opt4"],
            difficulty="expert"  # invalid difficulty
        )
    assert "Input should be 'easy', 'medium' or 'hard'" in str(excinfo.value)

def test_quiz_schema_correct_answers_forbidden():
    """Verify that correct answer or grading keys are forbidden in QuizQuestionPublic."""
    with pytest.raises(ValidationError) as excinfo:
        QuizQuestionPublic(
            id=uuid.uuid4(),
            question_text="Sample question?",
            options=["Opt1", "Opt2", "Opt3", "Opt4"],
            difficulty="hard",
            correct_answer="Opt1"  # forbidden extra key
        )
    assert "Extra inputs are not permitted" in str(excinfo.value)

# ──────────────────────────────────────────────────────────────────────
# 7. AI Endpoints Session validation matrix
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("endpoint_suffix", ["chat", "chat/stream", "summary", "quiz"])
@patch("app.api.v1.ai.validate_session_ownership_and_document", new_callable=AsyncMock)
def test_ai_endpoints_session_validation_success(mock_validate, endpoint_suffix, mock_auth):
    """Verify that a valid session succeeds session verification on all 4 AI routes."""
    mock_validate.return_value = {}
    
    with patch("app.api.v1.ai.ai_orchestrator_service.execute_query", new_callable=AsyncMock) as mock_exec, \
         patch("app.ai_system.orchestrator.document_guard.validate_document_access", new_callable=AsyncMock) as mock_access:
        mock_access.return_value = {"id": "doc-xyz", "upload_status": "ready", "chunk_count": 5}
        mock_exec.return_value = AIResponse(
            status="success", message="OK", execution_mode="single", tasks=[], citations=[], confidence=0.95
        )
        
        payload = {
            "session_id": "00000000-0000-0000-0000-000000000001",
            "message": "Explain this to me",
            "language": "en"
        }
        
        response = client.post(f"/api/v1/documents/doc-xyz/{endpoint_suffix}", json=payload)
        assert response.status_code in [200, 201, 202]
        mock_validate.assert_called_once_with("00000000-0000-0000-0000-000000000001", "doc-xyz", MOCK_USER, create_if_missing=True)

@pytest.mark.parametrize("endpoint_suffix", ["chat", "chat/stream", "summary", "quiz"])
def test_ai_endpoints_session_validation_failures(endpoint_suffix, mock_auth):
    """Verify that session verification failure propagates correct HTTP errors to all 4 AI routes."""
    
    # 1. Foreign user session is rejected (403)
    with patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock) as mock_get_session:
        mock_get_session.return_value = {
            "id": "00000000-0000-0000-0000-000000000001",
            "user_id": MOCK_FOREIGN_USER,
            "document_id": "doc-xyz"
        }
        payload = {"session_id": "00000000-0000-0000-0000-000000000001", "message": "query"}
        response = client.post(f"/api/v1/documents/doc-xyz/{endpoint_suffix}", json=payload)
        assert response.status_code == 403
        assert response.json()["detail"] == "SESSION_ACCESS_DENIED"

    # 2. Different-document session is rejected (400)
    with patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock) as mock_get_session:
        mock_get_session.return_value = {
            "id": "00000000-0000-0000-0000-000000000001",
            "user_id": MOCK_USER,
            "document_id": "doc-other"
        }
        payload = {"session_id": "00000000-0000-0000-0000-000000000001", "message": "query"}
        response = client.post(f"/api/v1/documents/doc-xyz/{endpoint_suffix}", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "SESSION_DOCUMENT_MISMATCH"

    # 3. Missing session with missing document is rejected (404)
    with patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock) as mock_get_session, \
         patch("app.services.session_service.document_repository.get_by_id", new_callable=AsyncMock) as mock_get_doc:
        mock_get_session.return_value = None
        mock_get_doc.return_value = None
        payload = {"session_id": "00000000-0000-0000-0000-000000000001", "message": "query"}
        response = client.post(f"/api/v1/documents/doc-xyz/{endpoint_suffix}", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "DOCUMENT_NOT_FOUND"

    # 4. Legacy document_id NULL session is rejected (400)
    with patch("app.services.session_service.chat_repository.get_chat_session", new_callable=AsyncMock) as mock_get_session:
        mock_get_session.return_value = {
            "id": "00000000-0000-0000-0000-000000000001",
            "user_id": MOCK_USER,
            "document_id": None
        }
        payload = {"session_id": "00000000-0000-0000-0000-000000000001", "message": "query"}
        response = client.post(f"/api/v1/documents/doc-xyz/{endpoint_suffix}", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "LEGACY_SESSION_REJECTED"

# ──────────────────────────────────────────────────────────────────────
# 8. Hardened Reprocess Concurrency & Failure Recovery tests
# ──────────────────────────────────────────────────────────────────────

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.atomic_update_status_reprocess", new_callable=AsyncMock)
def test_reprocess_concurrency_conflict(mock_atomic, mock_get_by_id, mock_auth):
    """Verify that if another concurrent request claims the document first, a 409 is returned."""
    mock_get_by_id.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "failed"
    }
    # atomic_update_status_reprocess returns None if the row is already claimed or updated by another transaction
    mock_atomic.return_value = None
    
    response = client.post("/api/v1/documents/doc-xyz/reprocess")
    assert response.status_code == 409
    assert response.json()["detail"] == "PROCESSING_OR_RETRY_ACTIVE"

@patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.atomic_update_status_reprocess", new_callable=AsyncMock)
@patch("app.db.repositories.chunk_repository.delete_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.mark_failed", new_callable=AsyncMock)
def test_reprocess_cleanup_failure_reverts_status(mock_mark_failed, mock_delete_chunks, mock_atomic, mock_get_by_id, mock_auth):
    """Verify that if chunk cleanup fails, status is reverted to failed, error_message is updated, and 500 is returned."""
    mock_get_by_id.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "failed"
    }
    mock_atomic.return_value = {
        "id": "doc-xyz",
        "user_id": MOCK_USER,
        "upload_status": "stored"
    }
    # chunk cleanup raises an operational database error
    mock_delete_chunks.side_effect = Exception("Supabase connection timed out during deletion")
    
    response = client.post("/api/v1/documents/doc-xyz/reprocess")
    assert response.status_code == 500
    assert "REPROCESSING_INITIALIZATION_FAILED" in response.json()["detail"]
    mock_mark_failed.assert_called_once_with("doc-xyz", "Reprocessing initialization failed: Supabase connection timed out during deletion")

# ──────────────────────────────────────────────────────────────────────
# 9. Stream Semantics & Failure Recovery tests
# ──────────────────────────────────────────────────────────────────────

import json
from app.schemas.ai_schema import DAGPlan, Task, TaskType, ExecutionMode, TaskResult

@patch("app.api.v1.ai.validate_session_ownership_and_document", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.validate_document_access", new_callable=AsyncMock)
@patch("app.ai_system.validation.input_validator.validate_input", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.planner.TaskPlanner.plan", new_callable=AsyncMock)
def test_stream_fatal_failure(mock_plan, mock_val_input, mock_access, mock_session, mock_auth):
    """Verify that a fatal planning failure halts the stream generator immediately."""
    mock_session.return_value = {}
    mock_access.return_value = {}
    
    mock_val_val = MagicMock()
    mock_val_val.valid = True
    mock_val_input.return_value = mock_val_val
    
    # Force planning failure
    mock_plan.side_effect = Exception("Fatal planning crash")
    
    payload = {"session_id": "00000000-0000-0000-0000-000000000001", "message": "hello"}
    response = client.post("/api/v1/documents/doc-xyz/chat/stream", json=payload)
    assert response.status_code == 200
    
    # Read stream chunks
    lines = [json.loads(line) for line in response.text.split("\n") if line.strip()]
    assert len(lines) > 0
    # The last yielded event should be the failed planning event
    last_event = lines[-1]
    assert last_event["stage"] == "planning"
    assert last_event["status"] == "failed"
    assert "Fatal planning crash" in last_event["message"]

@patch("app.api.v1.ai.validate_session_ownership_and_document", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.validate_document_access", new_callable=AsyncMock)
@patch("app.ai_system.validation.input_validator.validate_input", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.planner.TaskPlanner.plan", new_callable=AsyncMock)
def test_stream_non_fatal_task_failure(mock_plan, mock_val_input, mock_access, mock_session, mock_auth):
    """Verify that a non-primary task failure does not halt the stream, letting it complete with partial output."""
    mock_session.return_value = {}
    mock_access.return_value = {}
    
    mock_val_val = MagicMock()
    mock_val_val.valid = True
    mock_val_input.return_value = mock_val_val
    
    # Mock a plan with 2 tasks: 'key_points' (non-primary) and 'chat_answer' (primary intent)
    plan = DAGPlan(
        plan_id="plan-123",
        primary_intent=TaskType.CHAT_ANSWER,
        execution_mode=ExecutionMode.SEQUENTIAL,
        tasks=[
            Task(task_id="t-1", type=TaskType.KEY_POINTS, query="Extract key points"),
            Task(task_id="t-2", type=TaskType.CHAT_ANSWER, query="Generate answer")
        ]
    )
    mock_plan.return_value = plan
    
    # Mock runners
    async def mock_runner_t1(*args):
        raise Exception("Non-critical pipeline error")
        
    async def mock_runner_t2(*args):
        return TaskResult(task_id="t-2", type=TaskType.CHAT_ANSWER, status="success", content="Final answer text", confidence=0.9, citations=[])
        
    with patch("app.ai_system.orchestrator.pipeline_registry.PIPELINE_REGISTRY") as mock_registry:
        mock_registry.get.side_effect = lambda t: mock_runner_t1 if t == "key_points" else mock_runner_t2
        
        payload = {"session_id": "00000000-0000-0000-0000-000000000001", "message": "hello"}
        response = client.post("/api/v1/documents/doc-xyz/chat/stream", json=payload)
        assert response.status_code == 200
        
        lines = [json.loads(line) for line in response.text.split("\n") if line.strip()]
        stages = [l["stage"] for l in lines]
        statuses = [l["status"] for l in lines]
        
        # Verify key_points failed, but we still completed the chat_answer and overall query!
        assert "key_points" in stages
        assert "failed" in statuses
        assert "completed" in statuses
        assert lines[-1]["stage"] == "completed"
        assert lines[-1]["content"] == "Final answer text"

# ──────────────────────────────────────────────────────────────────────
# 10. CORS configuration unit test
# ──────────────────────────────────────────────────────────────────────

def test_cors_headers_present():
    """Verify that CORS response headers are returned and credentials are disallowed."""
    # Send preflight OPTIONS request
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers or response.headers.get("access-control-allow-credentials") == "false"
