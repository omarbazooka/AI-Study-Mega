import pytest
from app.schemas.ai_schema import ExecutionPlan, Task, PDFChatRequest, TaskResult, TaskType, ExecutionMode
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
from unittest.mock import AsyncMock, patch, MagicMock
from app.ai_system.orchestrator.errors import AllTasksFailedError

from app.ai_system.memory.memory_types import MemoryContext
from app.ai_system.retrieval.schemas import (
    RetrievalResult, RetrievalStatus, RetrievedChunk, Citation as RetrievalCitation
)

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
         patch("app.ai_system.validation.verifier.verify_response", new_callable=AsyncMock) as mock_verify:
        
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
            "id": "doc-ready-123",
            "user_id": "u1",
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
        
        async def mock_retrieve_side_effect(req, **kwargs):
            query_str = req.query if hasattr(req, "query") else str(req)
            if "outside" in query_str.lower():
                return RetrievalResult(
                    status=RetrievalStatus.NOT_FOUND,
                    confidence=0.0,
                    rewritten_query=query_str,
                    chunks=[],
                    context_text="",
                    citations=[]
                )
            return RetrievalResult(
                status=RetrievalStatus.FOUND,
                confidence=0.9,
                rewritten_query="photosynthesis",
                chunks=[
                    RetrievedChunk(
                        chunk_id="chunk-abc", document_id="doc-ready-123", user_id="u1",
                        text="Photosynthesis process.", score=0.9, page_number=1,
                    )
                ],
                context_text="[Chunk ID: chunk-abc | Page: 1 | Section: unknown | Score: 0.90]\nPhotosynthesis process.",
                citations=[RetrievalCitation(chunk_id="chunk-abc", page_number=1)],
            )
        mock_retrieve.side_effect = mock_retrieve_side_effect
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
        plan_id="plan-1",
        primary_intent=TaskType.SUMMARY,
        execution_mode=ExecutionMode.SINGLE,
        tasks=[
            Task(task_id="t1", type=TaskType.SUMMARY, query="Please summarize")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="Please summarize", language="en")
    
    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert response.execution_mode == ExecutionMode.SINGLE
    assert len(response.tasks) == 1
    assert response.tasks[0].type == TaskType.SUMMARY
    assert response.tasks[0].status == "success"
    assert "Grounded response for summary." in response.message
    assert len(response.citations) == 0


@pytest.mark.asyncio
async def test_orchestrator_parallel_success():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        plan_id="plan-2",
        primary_intent=TaskType.SUMMARY,
        execution_mode=ExecutionMode.PARALLEL,
        tasks=[
            Task(task_id="t1", type=TaskType.SUMMARY, query="summarize"),
            Task(task_id="t2", type=TaskType.QUIZ, query="quiz")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="summarize and quiz", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert len(response.tasks) == 2
    types = {t.type for t in response.tasks}
    assert TaskType.SUMMARY in types
    assert TaskType.QUIZ in types
    
    # Assert headers exist in merged response message
    assert "Summary" in response.message
    assert "Quiz" in response.message
    assert "Photosynthesis Quiz" in response.message


@pytest.mark.asyncio
async def test_orchestrator_sequential_with_dependency():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        plan_id="plan-3",
        primary_intent=TaskType.QUIZ,
        execution_mode=ExecutionMode.SEQUENTIAL,
        tasks=[
            Task(task_id="t1", type=TaskType.QUIZ, query="quiz"),
            Task(task_id="t2", type=TaskType.ANSWER_TABLE, query="answers", depends_on=["t1"])
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="quiz and answers", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert len(response.tasks) == 2
    
    ans_task = next(t for t in response.tasks if t.type == TaskType.ANSWER_TABLE)
    assert ans_task.status == "success"
    assert ans_task.metadata["consumed_quiz_questions"] is True
    assert "What is photosynthesis?" in ans_task.content


@pytest.mark.asyncio
async def test_orchestrator_all_no_answer():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        plan_id="plan-4",
        primary_intent=TaskType.CHAT_ANSWER,
        execution_mode=ExecutionMode.SINGLE,
        tasks=[
            Task(task_id="t1", type=TaskType.CHAT_ANSWER, query="outside the file")
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
        plan_id="plan-5",
        primary_intent=TaskType.UNKNOWN,
        execution_mode=ExecutionMode.SINGLE,
        tasks=[
            Task(task_id="t1", type=TaskType.UNKNOWN, query="test")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="test", language="en")

    with pytest.raises(AllTasksFailedError):
        await orchestrator.execute(plan, req)


@pytest.mark.asyncio
async def test_orchestrator_partial_failure():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        plan_id="plan-6",
        primary_intent=TaskType.SUMMARY,
        execution_mode=ExecutionMode.PARALLEL,
        tasks=[
            Task(task_id="t1", type=TaskType.SUMMARY, query="summarize"),
            Task(task_id="t2", type=TaskType.UNKNOWN, query="broken")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", document_id="doc-ready-123", message="summarize and broken", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "partial"
    assert "Grounded response for summary." in response.message
    assert response.confidence == 0.95
