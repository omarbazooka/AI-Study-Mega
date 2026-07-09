from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.ai_system.memory.memory_types import MemoryContext
from app.ai_system.retrieval.schemas import (
    RetrievalResult, RetrievalStatus, RetrievedChunk, Citation as RetrievalCitation
)

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


@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock)
@patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
def test_memory_contains_context_but_rag_returns_zero_chunks(
    mock_doc, mock_summarize, mock_store_save, mock_chat_save, mock_ctx, mock_retrieve
):
    """
    Critical Integration Test:
    Even if memory contains history, if RAG retrieval finds no relevant chunks,
    the response must fall back to the grounding fallback text:
    "لم أجد إجابة واضحة في الملف المرفوع."
    """
    mock_doc.return_value = {
        "id": "doc-empty-rag",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 5
    }
    # Memory has history for this student...
    mock_ctx.return_value = _mock_memory_context(session_summary="Student previously studied mitosis.")
    # ...but the RAG retriever finds nothing relevant for this specific query.
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.NO_RELEVANT_CONTEXT,
        reason="No relevant chunks found above threshold",
    )

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


@patch("app.ai_system.orchestrator.pipeline_registry.document_retriever.retrieve", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock)
@patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock)
@patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock)
@patch("app.db.repositories.document_repository.get_by_id")
def test_memory_and_retrieval_combine_on_success(
    mock_doc, mock_summarize, mock_store_save, mock_chat_save, mock_ctx, mock_retrieve
):
    """
    Positive-path integration test: when the retriever finds grounded chunks AND memory
    has personalization context, both flow into the same TaskResult - proving retrieval
    (app.ai_system.retrieval) and memory (app.ai_system.memory) are wired together rather
    than operating independently.
    """
    mock_doc.return_value = {
        "id": "doc-plant-101",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "upload_status": "ready",
        "chunk_count": 12
    }
    mock_ctx.return_value = _mock_memory_context(
        session_summary="Student is working through the Photosynthesis chapter.",
    )
    mock_retrieve.return_value = RetrievalResult(
        status=RetrievalStatus.FOUND,
        confidence=0.87,
        rewritten_query="photosynthesis chloroplast",
        chunks=[
            RetrievedChunk(
                chunk_id="chunk-1", document_id="doc-plant-101", user_id="00000000-0000-0000-0000-000000000000",
                text="Photosynthesis converts light energy into chemical energy.", score=0.91, page_number=4,
            )
        ],
        context_text="[Chunk ID: chunk-1 | Page: 4 | Section: unknown | Score: 0.91]\nPhotosynthesis converts light energy into chemical energy.",
        citations=[RetrievalCitation(chunk_id="chunk-1", page_number=4)],
    )

    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "session_id": "sess-test-success",
        "message": "explain photosynthesis",
        "language": "en",
        "user_level": "intermediate",
        "request_source": "chat"
    }

    response = client.post("/api/v1/documents/doc-plant-101/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    task = data["tasks"][0]
    assert task["status"] == "success"
    # Retrieval reached FOUND and fed real citations through to the response.
    assert task["citations"][0]["chunk_id"] == "chunk-1"
    assert task["citations"][0]["page_number"] == 4
    # Memory's session summary made it into this task's memory_info trace.
    assert task["metadata"]["memory_info"]["session_summary"] == "Student is working through the Photosynthesis chapter."
    # Retrieval's own status/confidence is now surfaced in the trace too.
    assert task["metadata"]["retrieval_info"]["status"] == "FOUND"
    assert task["metadata"]["retrieval_info"]["chunks_used"] == 1
