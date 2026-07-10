import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.schemas.ai_schema import VerificationPolicy, TaskType, Citation
from app.ai_system.retrieval.schemas import RetrievalResult, RetrievalStatus, RetrievedChunk, Citation as RetrievalCitation
from app.ai_system.orchestrator.verifier_client import VerificationResult
from app.ai_system.memory.memory_types import MemoryContext

client = TestClient(app)

def _mock_memory_context(**overrides):
    base = dict(
        user_profile=None,
        session_summary=None,
        weak_topics=[],
        recent_mistakes=[],
        relevant_past=[],
    )
    base.update(overrides)
    return MemoryContext(**base)

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.ai_system.services.llm.generate.llm_generate", new_callable=AsyncMock)
async def test_empty_retrieval_does_not_call_llm_and_returns_arabic_fallback(
    mock_llm_gen, mock_doc, mock_chunks, mock_retrieve
):
    """1. Empty retrieval does not call LLM and 2. Returns exactly the Arabic fallback response."""
    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    mock_chunks.return_value = [{"chunk_id": "c1", "embedding": [0.1] * 1536}]
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.NO_RELEVANT_CONTEXT,
        reason="No chunks found above similarity threshold"
    )

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "message": "tell me about photosynthesis",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_answer"
    assert data["message"] == "لم أجد إجابة واضحة في الملف المرفوع."
    mock_llm_gen.assert_not_called()

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
async def test_document_not_ready_blocks_planner_and_llm(
    mock_doc, mock_chunks, mock_retrieve
):
    """3. Document guard blocks execution before Planner/LLM when status is not ready."""
    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "processing",
        "chunk_count": 0
    }

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "message": "tell me about photosynthesis",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/chat", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "DOCUMENT_NOT_READY"
    mock_retrieve.assert_not_called()

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.ai_system.services.llm.generate.llm_generate", new_callable=AsyncMock)
async def test_out_of_scope_question_returns_fallback(
    mock_llm_gen, mock_doc, mock_chunks, mock_retrieve
):
    """4. Out-of-scope question on a valid PDF triggers prompt no-answer and returns fallback."""
    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    mock_chunks.return_value = [{"chunk_id": "c1", "embedding": [0.1] * 1536}]

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "message": "خارج الملف: explain how to build a spaceship",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_answer"
    assert data["message"] == "لم أجد إجابة واضحة في الملف المرفوع."
    mock_llm_gen.assert_not_called()

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.ai_system.services.llm.generate.llm_generate", new_callable=AsyncMock)
@patch("app.ai_system.services.llm.generation_service.GenerationService._execute_with_failover", new_callable=AsyncMock)
@patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock)
async def test_unsupported_claim_fails_verifier_and_triggers_fallback(
    mock_mem, mock_summarize, mock_store_save, mock_chat_save, mock_llm_judge, mock_llm_gen, mock_doc, mock_chunks, mock_retrieve
):
    """5. Unsupported LLM claim fails verifier and outputs fallback response immediately."""
    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    mock_chunks.return_value = [{"chunk_id": "c1", "embedding": [0.1] * 1536}]
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.FOUND,
        confidence=0.9,
        chunks=[RetrievedChunk(chunk_id="chunk-abc", document_id="00000000-0000-0000-0000-000000000101", user_id="u1", text="photosynthesis text", score=0.9)],
        context_text="photosynthesis text"
    )
    mock_mem.return_value = _mock_memory_context()
    
    from app.ai_system.services.llm.schemas import LLMResponsePayload, LLMUsageMetrics
    mock_llm_gen.return_value = LLMResponsePayload(
        task_id="t1",
        status="success",
        output_text="Mitosis is cell division",
        usage_metrics=LLMUsageMetrics(provider="groq", model="m1", key_alias="k1", input_tokens=10, output_tokens=5, total_tokens=15, latency_ms=100)
    )
    
    mock_llm_judge.return_value = {
        "text": '{"grounded": false, "grounding_score": 0.2, "suggested_action": "fallback", "reason": "unsupported", "unsupported_claims": ["Mitosis is cell division"]}'
    }

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "message": "tell me about photosynthesis",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_answer"
    assert data["message"] == "لم أجد إجابة واضحة في الملف المرفوع."

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.ai_system.services.llm.providers.groq_provider.GroqProvider.generate", new_callable=AsyncMock)
@patch("app.ai_system.services.llm.generation_service.GenerationService._execute_with_failover", new_callable=AsyncMock)
@patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.get_supabase_client")
async def test_large_document_quiz_uses_map_reduce_routed_by_token_budget(
    mock_supabase_getter, mock_mem, mock_summarize, mock_store_save, mock_chat_save, mock_llm_judge, mock_groq_gen, mock_doc, mock_chunks, mock_retrieve
):
    """6. Summary/Quiz for large document uses Map-Reduce when token budget (characters // 3) > 3000."""
    from unittest.mock import MagicMock
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
            return MagicMock(data=[
                {
                    "id": f"chunk-{i}",
                    "content": f"Photosynthesis process cell chloroplast light final quiz results summary generated for testing the map-reduce mechanism. {i}",
                    "page_start": 1,
                    "chunk_index": i
                }
                for i in range(10)
            ])
        return MagicMock(data=[])
        
    mock_query.execute.side_effect = execute_side_effect
    mock_supabase_getter.return_value = mock_supabase

    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    mock_chunks.return_value = [{"chunk_id": "c1", "embedding": [0.1] * 1536}]
    mock_mem.return_value = _mock_memory_context()
    
    large_chunks = [
        RetrievedChunk(
            chunk_id=f"chunk-{i}", document_id="00000000-0000-0000-0000-000000000101", user_id="u1",
            text="Photosynthesis process cell chloroplast light final quiz results summary generated for testing the map-reduce mechanism. " * 50, score=0.9
        )
        for i in range(10)
    ]
    
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.FOUND,
        confidence=0.9,
        chunks=large_chunks,
        context_text="large context"
    )

    mock_groq_gen.side_effect = [
        {"text": "Map output"},
        {"text": "Final quiz results summary generated for testing the map-reduce mechanism."}
    ]
    
    mock_llm_judge.return_value = {
        "text": '{"grounded": true, "grounding_score": 1.0, "suggested_action": "pass", "reason": "OK"}'
    }

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/summary", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert mock_groq_gen.call_count >= 2

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.ai_system.services.llm.generate.llm_generate", new_callable=AsyncMock)
@patch("app.ai_system.services.llm.generation_service.GenerationService._execute_with_failover", new_callable=AsyncMock)
@patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock)
async def test_citations_only_reference_retrieved_chunks(
    mock_mem, mock_summarize, mock_store_save, mock_chat_save, mock_llm_judge, mock_llm_gen, mock_doc, mock_chunks, mock_retrieve
):
    """7. Citations only reference real retrieved chunk IDs."""
    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    mock_chunks.return_value = [{"chunk_id": "c1", "embedding": [0.1] * 1536}]
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.FOUND,
        confidence=0.9,
        chunks=[
            RetrievedChunk(chunk_id="chunk-photo-1", document_id="00000000-0000-0000-0000-000000000101", user_id="u1", text="chloroplast converts sunlight", score=0.9)
        ],
        context_text="chloroplast converts sunlight"
    )
    mock_mem.return_value = _mock_memory_context()

    from app.ai_system.services.llm.schemas import LLMResponsePayload, LLMUsageMetrics
    mock_llm_gen.return_value = LLMResponsePayload(
        task_id="t1",
        status="success",
        output_text="Sunlight is converted inside the chloroplast.",
        usage_metrics=LLMUsageMetrics(provider="g", model="m", key_alias="k", input_tokens=10, output_tokens=5, total_tokens=15, latency_ms=100)
    )
    
    mock_llm_judge.return_value = {
        "text": '{"grounded": true, "grounding_score": 1.0, "suggested_action": "pass", "reason": "OK"}'
    }

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "message": "sunlight and chloroplast",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["citations"]) == 1
    assert data["citations"][0]["chunk_id"] == "chunk-photo-1"

@pytest.mark.asyncio
@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.document_guard.get_chunks_by_document", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
@patch("app.ai_system.services.llm.generate.llm_generate", new_callable=AsyncMock)
@patch("app.ai_system.services.llm.generation_service.GenerationService._execute_with_failover", new_callable=AsyncMock)
@patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock)
async def test_response_trace_stages_exist(
    mock_mem, mock_summarize, mock_store_save, mock_chat_save, mock_llm_judge, mock_llm_gen, mock_doc, mock_chunks, mock_retrieve
):
    """8. Final successful response contains all trace stages in metadata."""
    mock_doc.return_value = {
        "id": "00000000-0000-0000-0000-000000000101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    mock_chunks.return_value = [{"chunk_id": "c1", "embedding": [0.1] * 1536}]
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.FOUND,
        confidence=0.9,
        chunks=[
            RetrievedChunk(chunk_id="c1", document_id="00000000-0000-0000-0000-000000000101", user_id="u1", text="photosynthesis process", score=0.9)
        ],
        context_text="photosynthesis process"
    )
    mock_mem.return_value = _mock_memory_context()

    from app.ai_system.services.llm.schemas import LLMResponsePayload, LLMUsageMetrics
    mock_llm_gen.return_value = LLMResponsePayload(
        task_id="t1",
        status="success",
        output_text="photosynthesis details text.",
        usage_metrics=LLMUsageMetrics(provider="g", model="m", key_alias="k", input_tokens=10, output_tokens=5, total_tokens=15, latency_ms=100)
    )
    
    mock_llm_judge.return_value = {
        "text": '{"grounded": true, "grounding_score": 1.0, "suggested_action": "pass", "reason": "OK"}'
    }

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test",
        "message": "tell me about photosynthesis",
        "language": "ar"
    }

    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000101/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "trace" in data["metadata"]
    
    stages = [item["stage"] for item in data["metadata"]["trace"]]
    assert "document_guard" in stages
    assert "input_validation" in stages
    assert "planner" in stages
    assert "retriever" in stages
    assert "executor" in stages
    assert "verifier" in stages
    assert "citations" in stages
    assert "save_chat_state" in stages
