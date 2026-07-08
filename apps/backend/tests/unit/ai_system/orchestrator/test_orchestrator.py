import pytest
from app.schemas.ai_schema import ExecutionPlan, Task, PDFChatRequest, TaskResult
from app.ai_system.orchestrator.orchestrator import TaskOrchestrator
from app.ai_system.orchestrator.constants import (
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL,
    NO_ANSWER_FALLBACK
)
from unittest.mock import AsyncMock, patch
from app.ai_system.orchestrator.errors import AllTasksFailedError

from app.ai_system.memory.memory_types import MemoryContext

@pytest.fixture(autouse=True)
def mock_db_and_memory():
    with patch("app.db.repositories.chunk_repository.get_chunks_by_document", new_callable=AsyncMock) as mock_chunks, \
         patch("app.db.repositories.chat_repository.save_message", new_callable=AsyncMock) as mock_save, \
         patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever.get_memory_context", new_callable=AsyncMock) as mock_ctx, \
         patch("app.ai_system.orchestrator.pipeline_registry.store.save_message", new_callable=AsyncMock) as mock_store_save, \
         patch("app.ai_system.orchestrator.pipeline_registry.summarizer.summarize_session", new_callable=AsyncMock) as mock_sum, \
         patch("app.ai_system.orchestrator.pipeline_registry.llm_generate", new_callable=AsyncMock) as mock_llm_gen:
        
        mock_chunks.return_value = [{"id": "chunk-abc", "content": "Photosynthesis process.", "user_id": "u1", "chunk_index": 0}]
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



@pytest.mark.asyncio
async def test_orchestrator_single_success():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_SINGLE,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="Please summarize")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="Please summarize", language="en")
    
    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert response.execution_mode == MODE_SINGLE
    assert len(response.tasks) == 1
    assert response.tasks[0].type == TASK_SUMMARY
    assert response.tasks[0].status == "success"
    assert response.tasks[0].metadata["mock"] is False
    assert response.message == "Grounded response for summary."
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "chunk-abc"


@pytest.mark.asyncio
async def test_orchestrator_parallel_success():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_PARALLEL,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="summarize"),
            Task(task_id="t2", type=TASK_QUIZ, query="quiz")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="summarize and quiz", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert len(response.tasks) == 2
    types = {t.type for t in response.tasks}
    assert TASK_SUMMARY in types
    assert TASK_QUIZ in types
    
    # Assert headers exist in merged response message
    assert "Summary" in response.message
    assert "Quiz" in response.message
    assert "Photosynthesis Quiz" in response.message


@pytest.mark.asyncio
async def test_orchestrator_sequential_with_dependency():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_SEQUENTIAL,
        tasks=[
            Task(task_id="t1", type=TASK_QUIZ, query="quiz"),
            Task(task_id="t2", type=TASK_ANSWER_TABLE, query="answers", depends_on=["t1"])
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="quiz and answers", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert len(response.tasks) == 2
    
    ans_task = next(t for t in response.tasks if t.type == TASK_ANSWER_TABLE)
    assert ans_task.status == "success"
    assert ans_task.metadata["consumed_quiz_questions"] is True
    assert "What is photosynthesis?" in ans_task.content


@pytest.mark.asyncio
async def test_orchestrator_all_no_answer():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_SINGLE,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="outside the file")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="outside the file", language="ar")

    response = await orchestrator.execute(plan, req)
    assert response.status == "no_answer"
    assert response.message == NO_ANSWER_FALLBACK
    assert response.confidence == 0.0
    assert len(response.citations) == 0


@pytest.mark.asyncio
async def test_orchestrator_all_failed_raises_exception():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_SINGLE,
        tasks=[
            Task(task_id="t1", type="nonexistent_type", query="test")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="test", language="en")

    with pytest.raises(AllTasksFailedError):
        await orchestrator.execute(plan, req)


@pytest.mark.asyncio
async def test_orchestrator_partial_failure():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_PARALLEL,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="summarize"),
            Task(task_id="t2", type="broken_pipeline", query="broken")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="summarize and broken", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "partial"
    assert response.message == "Grounded response for summary."
    assert response.confidence == 0.9
