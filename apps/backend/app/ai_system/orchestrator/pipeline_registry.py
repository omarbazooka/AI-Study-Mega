import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.schemas.ai_schema import Task, TaskResult, Citation
from app.ai_system.orchestrator.constants import (
    TASK_CHAT_ANSWER,
    TASK_EXPLAIN,
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    TASK_KEY_POINTS,
    TASK_COMPARISON_TABLE,
    NO_ANSWER_FALLBACK
)
from app.db.repositories import chunk_repository, chat_repository
from app.ai_system.memory import (
    MemoryRetriever, PersonalizationEngine, build_grounded_prompt,
    MemoryStore, ChatMessage, Summarizer
)
from app.ai_system.services.llm.generate import generate as llm_generate
from app.ai_system.services.llm.schemas import (
    LLMEngineerPayload, SourceInfo, StrictGroundingPolicy,
    ExpectedLLMOutputFormat, ChunkContext, MemoryContext
)

logger = logging.getLogger(__name__)

MOCK_CONFIDENCE = 0.9

memory_retriever = MemoryRetriever()
personalizer = PersonalizationEngine()
store = MemoryStore()
summarizer = Summarizer()

def check_no_answer_trigger(query: str) -> bool:
    """Checks if query simulates requesting information outside the document context."""
    normalized = query.lower()
    return "خارج الملف" in normalized or "outside the file" in normalized

async def execute_common_pipeline_steps(
    task: Task, request: Any, task_type: str, precomputed_content: Optional[str] = None
) -> TaskResult:
    """
    Executes core pipeline steps using either the real LLM GenerationService
    or precomputed content (for answer tables).
    """
    # 1. Check intent triggers
    if check_no_answer_trigger(task.query):
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="no_answer",
            content=NO_ANSWER_FALLBACK,
            citations=[],
            confidence=0.0,
            metadata={"mock": False, "retrieval_mode": "temporary_chunk_context_until_rag"}
        )

    user_id = getattr(request, "user_id", "00000000-0000-0000-0000-000000000000")
    session_id = getattr(request, "session_id", "sess-xyz")
    document_id = getattr(request, "document_id", None)
    lang = getattr(request, "language", "ar")

    # 2. Retrieve document chunks
    chunks = []
    if document_id:
        chunks = await chunk_repository.get_chunks_by_document(document_id)
        # 3. Check for empty RAG context -> strict fallback without calling LLM
        if not chunks:
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="no_answer",
                content=NO_ANSWER_FALLBACK,
                citations=[],
                confidence=0.0,
                metadata={"mock": False, "retrieval_mode": "temporary_chunk_context_until_rag"}
            )

    # 4. Save user message to chat database
    user_msg = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=task.query,
        topic=task.metadata.get("topic")
    )
    await store.save_message(user_msg)

    # 5. Temporary context selection
    # For chat/explain/key_points/comparison_table use first 3 to 5 chunks
    # For summary/quiz use all chunks (capped at 30 to prevent context overflow)
    if task_type in [TASK_CHAT_ANSWER, TASK_EXPLAIN, TASK_KEY_POINTS, TASK_COMPARISON_TABLE]:
        selected_chunks = chunks[:5]
    else:
        selected_chunks = chunks[:30]

    # Convert retrieved chunks to ChunkContext Pydantic objects
    retrieved_context = []
    chunk_page_map = {}
    for idx, c in enumerate(selected_chunks):
        cid = str(c.get("id", idx))
        page_num = c.get("page_start", 1)
        chunk_page_map[cid] = page_num
        retrieved_context.append(
            ChunkContext(
                chunk_id=cid,
                page_number=page_num,
                score=0.9 - (0.02 * idx),
                content=c.get("content", "")
            )
        )

    # 6. Execute task using precomputed content or LLM generation
    content_result = ""
    usage_metrics = None

    if precomputed_content is not None:
        content_result = precomputed_content
        logger.info(f"Using precomputed content for task {task.task_id} (type: {task_type})")
        source_chunk_ids = [c.chunk_id for c in retrieved_context[:3]]
    else:
        # Build LLMEngineerPayload
        output_type = "text"
        if task_type == TASK_QUIZ:
            output_type = "quiz"
        elif task_type == TASK_SUMMARY:
            output_type = "summary"
        elif task_type == TASK_EXPLAIN:
            output_type = "explanation"

        expected_format = ExpectedLLMOutputFormat(
            type=output_type,
            question_count=5 if task_type == TASK_QUIZ else None,
            must_be_grounded=True,
            must_not_use_general_knowledge=True
        )

        memory_payload = MemoryContext(
            quiz_difficulty=getattr(request, "difficulty", "medium"),
            preferred_language=lang
        )

        payload = LLMEngineerPayload(
            task_id=task.task_id,
            task_type=task_type,
            pipeline_type="standard_rag",
            original_user_query=task.query,
            task_query=task.query,
            source=SourceInfo(source_id=str(document_id), source_type="document"),
            retrieved_document_context=retrieved_context,
            memory_context=memory_payload,
            strict_grounding_policy=StrictGroundingPolicy(
                academic_source_of_truth="retrieved_document_context_only",
                memory_usage="personalization_only",
                if_document_context_insufficient=NO_ANSWER_FALLBACK
            ),
            expected_llm_output_format=expected_format
        )

        llm_response = await llm_generate(payload)

        if llm_response.status == "failure":
            logger.error(f"LLM task execution failed: {llm_response.error_message}")
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="failure",
                content="عذراً، فشل النظام في معالجة طلبك.",
                citations=[],
                confidence=0.0,
                metadata={"mock": False, "error": llm_response.error_message}
            )

        if llm_response.output_text:
            content_result = llm_response.output_text
        elif llm_response.output_json:
            content_result = json.dumps(llm_response.output_json, ensure_ascii=False)
        
        source_chunk_ids = llm_response.source_chunk_ids
        usage_metrics = llm_response.usage_metrics.model_dump() if llm_response.usage_metrics else None

    # 7. Save assistant response
    retrieved_chunk_ids = [c.chunk_id for c in retrieved_context]
    source_chunk_id = retrieved_chunk_ids[0] if retrieved_chunk_ids else None

    await chat_repository.save_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=content_result,
        topic=task.metadata.get("topic"),
        retrieved_chunks=retrieved_chunk_ids,
        source_chunk_id=source_chunk_id
    )

    # 8. Build citations
    citations = [
        Citation(chunk_id=cid, page_number=chunk_page_map.get(cid, 1), score=0.9)
        for cid in source_chunk_ids
    ]

    metadata = {
        "mock": False,
        "document_id": document_id,
        "retrieval_mode": "temporary_chunk_context_until_rag",
        "usage_metrics": usage_metrics
    }

    # Quiz questions caching for answer table consumption
    if task_type == TASK_QUIZ and precomputed_content is None and llm_response.output_json:
        questions = llm_response.output_json.get("questions", [])
        result_questions = []
        for idx, q in enumerate(questions):
            result_questions.append({
                "id": f"q{idx+1}",
                "question": q.get("question"),
                "options": q.get("options"),
                "correct": q.get("correct_answer")
            })
        metadata["generated_questions"] = result_questions

    return TaskResult(
        task_id=task.task_id,
        type=task_type,
        status="success" if content_result != NO_ANSWER_FALLBACK else "no_answer",
        content=content_result,
        citations=citations,
        confidence=MOCK_CONFIDENCE,
        metadata=metadata
    )


async def run_chat_answer_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Localized QA search pipeline using vector chunks (top-k)."""
    return await execute_common_pipeline_steps(task, request, TASK_CHAT_ANSWER)

async def run_explain_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Explanation pipeline for a targeted segment."""
    return await execute_common_pipeline_steps(task, request, TASK_EXPLAIN)

async def run_summary_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level summary utilizing all chunks."""
    return await execute_common_pipeline_steps(task, request, TASK_SUMMARY)

async def run_quiz_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level quiz generator utilizing all chunks."""
    return await execute_common_pipeline_steps(task, request, TASK_QUIZ)

async def run_answer_table_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates an answer table based on previous quiz questions."""
    lang = getattr(request, "language", "ar")
    
    # Check if we can dynamically consume quiz questions from previous tasks
    questions = []
    if previous_results:
        for res in previous_results.values():
            metadata = getattr(res, "metadata", {}) or {}
            if not metadata and isinstance(res, dict):
                metadata = res.get("metadata", {})
            if metadata and "generated_questions" in metadata:
                questions = metadata["generated_questions"]
                break

    if questions:
        rows = []
        if lang == "ar":
            rows.append("### جدول الإجابات النموذجية")
            rows.append("| السؤال | الإجابة الصحيحة |")
            rows.append("|---|---|")
            for q in questions:
                rows.append(f"| {q['question']} | {q['correct']} |")
        else:
            rows.append("### Answers Table")
            rows.append("| Question | Correct Answer |")
            rows.append("|---|---|")
            for q in questions:
                rows.append(f"| {q['question']} | {q['correct']} |")
        table_content = "\n".join(rows)
        result = await execute_common_pipeline_steps(task, request, TASK_ANSWER_TABLE, precomputed_content=table_content)
        if result.status == "success":
            result.metadata["consumed_quiz_questions"] = True
        return result
    
    # If no previous quiz was run, let LLM generate the answer table from scratch
    return await execute_common_pipeline_steps(task, request, TASK_ANSWER_TABLE)

async def run_key_points_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Extracts key points."""
    return await execute_common_pipeline_steps(task, request, TASK_KEY_POINTS)

async def run_comparison_table_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates comparison tables."""
    return await execute_common_pipeline_steps(task, request, TASK_COMPARISON_TABLE)

# Global Registry
PIPELINE_REGISTRY: Dict[str, Any] = {
    TASK_CHAT_ANSWER: run_chat_answer_pipeline,
    TASK_EXPLAIN: run_explain_pipeline,
    TASK_SUMMARY: run_summary_pipeline,
    TASK_QUIZ: run_quiz_pipeline,
    TASK_ANSWER_TABLE: run_answer_table_pipeline,
    TASK_KEY_POINTS: run_key_points_pipeline,
    TASK_COMPARISON_TABLE: run_comparison_table_pipeline
}
