import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

from app.ai_system.memory.memory_types import MemoryContext
from app.ai_system.retrieval.schemas import RetrievalResult, RetrievalStatus, RetrievedChunk

@pytest.fixture(autouse=True)
def mock_db_and_memory():
    with patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock) as mock_retrieve, \
         patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock) as mock_save, \
         patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock) as mock_ctx, \
         patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock) as mock_store_save, \
         patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock) as mock_sum, \
         patch("app.ai_system.orchestrator.pipeline_registry.llm_generate", new_callable=AsyncMock) as mock_llm_gen, \
         patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock) as mock_doc_get, \
         patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock) as mock_chunks_get, \
         patch("app.ai_system.services.llm.providers.groq_provider.GroqProvider.generate", new_callable=AsyncMock) as mock_groq_gen, \
         patch("app.ai_system.orchestrator.pipeline_registry.get_supabase_client") as mock_supabase_getter, \
         patch("app.ai_system.validation.verifier.verify_response", new_callable=AsyncMock) as mock_verify, \
         patch("app.api.v1.ai.validate_session_ownership_and_document", new_callable=AsyncMock) as mock_validate:
        
        mock_validate.return_value = {}
        
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.insert.return_value = mock_query
        mock_query.update.return_value = mock_query
        
        def execute_side_effect():
            call_args = mock_supabase.table.call_args_list
            if call_args and call_args[-1][0][0] == "document_chunks":
                data = [
                    {
                        "id": "chunk-abc",
                        "content": "Photosynthesis process.",
                        "page_start": 1,
                        "chunk_index": 0
                    }
                ]
                return MagicMock(data=data)
            return MagicMock(data=[])
            
        mock_query.execute.side_effect = execute_side_effect
        mock_supabase_getter.return_value = mock_supabase

        async def mock_groq_gen_side_effect(model, prompt, **kwargs):
            if "quiz" in prompt.lower() or "quiz" in kwargs.get("system_prompt", "").lower():
                return {
                    "text": '{"title": "Photosynthesis Quiz", "questions": [{"question_text": "What is photosynthesis?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct_option_id": 0, "explanation": "Detailed explanation", "concept": "Photosynthesis concept", "difficulty": "medium"}]}',
                    "input_tokens": 10,
                    "output_tokens": 10,
                    "latency_ms": 100
                }
            return {
                "text": "Grounded response for summary.",
                "input_tokens": 10,
                "output_tokens": 10,
                "latency_ms": 100
            }
        mock_groq_gen.side_effect = mock_groq_gen_side_effect
        
        mock_doc_get.return_value = {
            "id": "00000000-0000-0000-0000-000000000123",
            "user_id": "00000000-0000-0000-0000-000000000000",
            "upload_status": "ready",
            "chunk_count": 5
        }
        mock_chunks_get.return_value = [{"chunk_id": "chunk-abc", "embedding": [0.1] * 1536}]
        
        async def mock_verify_side_effect(user_query, task_type, retrieved_chunks, executor_output, **kwargs):
            from app.ai_system.validation.schemas import VerificationResult as ValVerificationResult, VerifierAction
            return ValVerificationResult(
                passed=True,
                action=VerifierAction.RETURN,
                confidence=0.9,
                reasons=[],
                unsupported_claims=[],
                citations=[],
                final_answer=executor_output,
                metadata={}
            )
        mock_verify.side_effect = mock_verify_side_effect
        
        mock_retrieve.return_value = RetrievalResult(
            status=RetrievalStatus.FOUND,
            confidence=0.9,
            chunks=[
                RetrievedChunk(
                    chunk_id="chunk-abc", document_id="00000000-0000-0000-0000-000000000123", user_id="u1",
                    text="Photosynthesis process.", score=0.9, page_number=1,
                )
            ],
            context_text="[Chunk ID: chunk-abc | Page: 1 | Section: unknown | Score: 0.90]\nPhotosynthesis process.",
        )
        mock_ctx.return_value = MemoryContext(
            user_profile=None,
            session_summary=None,
            weak_topics=[],
            recent_mistakes=[],
            relevant_past=[]
        )

        async def mock_generate_side_effect(payload):
            from app.ai_system.services.llm.schemas import LLMResponsePayload, LLMUsageMetrics
            if payload.task_type in ["quiz", "quiz_generation"]:
                return LLMResponsePayload(
                    task_id=payload.task_id,
                    status="success",
                    output_json={
                        "quiz_title": "Photosynthesis Quiz",
                        "difficulty": "medium",
                        "questions": [
                            {
                                "question": "What is photosynthesis?",
                                "type": "mcq",
                                "options": ["Option A", "Option B", "Option C", "Option D"],
                                "correct_answer": "Option A",
                                "explanation": "Detailed explanation",
                                "source_chunk_ids": ["chunk-abc"]
                            }
                        ]
                    },
                    source_chunk_ids=["chunk-abc"],
                    usage_metrics=LLMUsageMetrics(
                        provider="groq",
                        model="llama-3.3-70b-versatile",
                        key_alias="REASONING_KEY_1",
                        input_tokens=150,
                        output_tokens=100,
                        total_tokens=250,
                        latency_ms=180
                    )
                )
            return LLMResponsePayload(
                task_id=payload.task_id,
                status="success",
                output_text=f"Grounded response for {payload.task_type}.",
                source_chunk_ids=["chunk-abc"],
                usage_metrics=LLMUsageMetrics(
                    provider="groq",
                    model="llama-3.1-8b-instant",
                    key_alias="FAST_KEY_1",
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    latency_ms=120
                )
            )
        
        mock_llm_gen.side_effect = mock_generate_side_effect
        yield


client = TestClient(app)

# Standard mock document details
MOCK_USER = "00000000-0000-0000-0000-000000000000"
MOCK_READY_DOC = {
    "id": "00000000-0000-0000-0000-000000000123",
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
MOCK_READY_ZERO_CHUNKS_DOC = {
    "id": "doc-ready-zero",
    "user_id": MOCK_USER,
    "upload_status": "ready",
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
        "session_id": "00000000-0000-0000-0000-000000000001",
        "message": "لخصلي الملف واعمل quiz",
        "language": "ar",
        "user_level": "intermediate",
        "request_source": "chat"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000123/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Summary" in data["message"]
    assert "Quiz" in data["message"]
    assert len(data["tasks"]) == 2
    assert data["confidence"] == 0.95


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_document_not_ready(mock_repo):
    """Verifies that un-indexed documents are rejected by Document Guard."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_NOT_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "00000000-0000-0000-0000-000000000001",
        "message": "Explain this to me",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-not-ready/chat", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "DOCUMENT_NOT_READY"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_ready_but_zero_chunks(mock_repo):
    """Verifies that documents marked ready but having chunk_count=0 are rejected."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_READY_ZERO_CHUNKS_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "00000000-0000-0000-0000-000000000001",
        "message": "Hello",
        "language": "en"
    }

    response = client.post("/api/v1/documents/doc-ready-zero/chat", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "DOCUMENT_NOT_READY"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_chat_endpoint_access_denied(mock_repo):
    """Verifies ownership check fails when document is owned by a different user."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_FOREIGN_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "00000000-0000-0000-0000-000000000001",
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
        "session_id": "00000000-0000-0000-0000-000000000001",
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
        "session_id": "00000000-0000-0000-0000-000000000001",
        "message": "hi",
        "language": "en"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000123/chat", json=payload)
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
        "session_id": "00000000-0000-0000-0000-000000000001",
        "language": "en",
        "user_level": "beginner",
        "summary_style": "bullet_points"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000123/summary", json=payload)
    if response.status_code != 200:
        print("SUMMARY FAIL DETAIL:", response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Grounded response for summary" in data["message"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["type"] == "summary"


@patch("app.ai_system.orchestrator.document_guard.document_repository")
def test_quiz_shortcut_success(mock_repo):
    """Verifies the quiz shortcut endpoint execution."""
    mock_repo.get_by_id = AsyncMock(return_value=MOCK_READY_DOC)

    payload = {
        "user_id": MOCK_USER,
        "session_id": "00000000-0000-0000-0000-000000000001",
        "language": "en",
        "user_level": "intermediate",
        "difficulty": "medium",
        "number_of_questions": 5,
        "question_type": "multiple_choice"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000123/quiz", json=payload)
    if response.status_code != 200:
        print("QUIZ FAIL DETAIL:", response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Photosynthesis Quiz" in data["message"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["type"] == "quiz"
