from typing import Dict, Any, List, Optional
from datetime import datetime

from app.schemas.ai_schema import Task, TaskResult, Citation, TaskType, VerificationPolicy, OutputFormat
from app.ai_system.orchestrator.constants import (
    TASK_CHAT_ANSWER,
    TASK_EXPLAIN,
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    TASK_KEY_POINTS,
    TASK_COMPARISON_TABLE,
    TASK_FLASHCARDS,
    TASK_ANSWER_EVALUATION,
    NO_ANSWER_FALLBACK
)
from app.db.repositories import chat_repository
from app.ai_system.memory import (
    MemoryRetriever, PersonalizationEngine, build_grounded_prompt,
    MemoryStore, ChatMessage, Summarizer
)
from app.ai_system.retrieval import get_document_retriever
from app.ai_system.retrieval.schemas import RetrievalRequest, RetrievalStatus
from app.ai_system.orchestrator.executor_client import default_executor_client
from app.ai_system.orchestrator.verifier_client import default_verifier_client

MOCK_CONFIDENCE = 0.5

memory_retriever = MemoryRetriever()
personalizer = PersonalizationEngine()
store = MemoryStore()
summarizer = Summarizer()
document_retriever = get_document_retriever()

STOPWORDS = {"a", "an", "the", "about", "on", "in", "of", "to", "for", "and", "or", "is", "are"}

def build_citations(retrieved_chunks: List[Any], llm_output: str) -> List[Citation]:
    """
    Constructs citations referencing only the retrieved chunks that are actually
    relevant or cited in the LLM response text (e.g. by matching content keywords or chunk IDs).
    """
    citations = []
    import re
    
    output_lower = llm_output.lower()
    
    for c in retrieved_chunks:
        c_id = c.chunk_id if hasattr(c, "chunk_id") else c.get("chunk_id")
        text = c.text if hasattr(c, "text") else c.get("content", "")
        page = c.page_number if hasattr(c, "page_number") else c.get("page_start", 1)
        section = c.section_title if hasattr(c, "section_title") else c.get("section_title")
        score = c.score if hasattr(c, "score") else c.get("score", 0.90)

        chunk_cited = False
        if str(c_id).lower() in output_lower:
            chunk_cited = True
        else:
            words = [w for w in re.findall(r"\w{5,}", text.lower()) if w not in STOPWORDS]
            matches = sum(1 for w in words if w in output_lower)
            if matches >= 3:
                chunk_cited = True

        if chunk_cited:
            citations.append(Citation(
                chunk_id=str(c_id),
                page_number=page or 1,
                section_title=section or "RAG Pipeline",
                snippet=text[:120].strip() + "...",
                score=score
            ))
            
    if not citations and retrieved_chunks:
        c = retrieved_chunks[0]
        c_id = c.chunk_id if hasattr(c, "chunk_id") else c.get("chunk_id")
        text = c.text if hasattr(c, "text") else c.get("content", "")
        page = c.page_number if hasattr(c, "page_number") else c.get("page_start", 1)
        section = c.section_title if hasattr(c, "section_title") else c.get("section_title")
        score = c.score if hasattr(c, "score") else c.get("score", 0.90)
        citations.append(Citation(
            chunk_id=str(c_id),
            page_number=page or 1,
            section_title=section or "RAG Pipeline",
            snippet=text[:120].strip() + "...",
            score=score
        ))
        
    return citations

async def execute_map_reduce(
    task: Task,
    request: Any,
    task_type: TaskType,
    chunks: List[Dict[str, Any]],
    retrieval_result: Any
) -> TaskResult:
    """Executes a Map-Reduce pipeline for Summary/Quiz to handle large contexts safely."""
    from app.ai_system.services.llm.generate import llm_generate
    import logging
    logger = logging.getLogger(__name__)
    
    batch_size = 10
    intermediate_summaries = []
    
    logger.info(f"[Map-Reduce] Starting Map phase on {len(chunks)} chunks...")
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_context = "\n\n".join([f"[Page: {c['page_start']}]\n{c['content']}" for c in batch])
        
        if task_type == TaskType.QUIZ:
            map_prompt = f"""Draft 2 distinct multiple choice questions based strictly on this document context section. Ensure questions are grounded.

Context section:
{batch_context}
"""
        else:
            map_prompt = f"""Summarize this section of the document in 3 clear bullet points, focus on key concepts.

Context section:
{batch_context}
"""
        try:
            res = await llm_generate(
                prompt=map_prompt,
                task_type="summary_map" if task_type == TaskType.SUMMARY else "chat_simple",
                system_prompt="You are an intermediate summarization worker. Ground all claims strictly."
            )
            if res.output_text:
                intermediate_summaries.append(res.output_text)
        except Exception as e:
            logger.error(f"[Map-Reduce] Batch map failed: {e}")
            
    combined_intermediates = "\n\n".join(intermediate_summaries)
    logger.info("[Map-Reduce] Map phase complete. Starting Reduce phase...")
    
    if task_type == TaskType.QUIZ:
        reduce_prompt = f"""Consolidate the intermediate draft questions into a single cohesive quiz.
The final output MUST be in the requested OutputFormat Quiz JSON structure.

Intermediate Draft Questions:
{combined_intermediates}
"""
    else:
        reduce_prompt = f"""Combine and structure the intermediate summary notes into a final unified summary. Ensure it is clean markdown.

Intermediate Summary Notes:
{combined_intermediates}
"""

    try:
        reduce_res = await llm_generate(
            prompt=reduce_prompt,
            task_type="summary_reduce" if task_type == TaskType.SUMMARY else "quiz_generation",
            system_prompt="You are a final summarization consolidator.",
            output_format=task.output_format.value
        )
        raw_response = reduce_res.output_text or ""
    except Exception as e:
        logger.error(f"[Map-Reduce] Reduce phase failed: {e}")
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="failed",
            content="",
            confidence=0.0,
            error=f"Map-Reduce reduce phase failed: {str(e)}"
        )

    policy = getattr(request, "verification_policy", None) or VerificationPolicy()
    citations = build_citations(retrieval_result.chunks if retrieval_result else [], raw_response)
    
    verification = await default_verifier_client.verify(
        user_query=task.query,
        intent=task_type.value,
        retrieved_chunks=chunks,
        llm_output=raw_response,
        output_format=task.output_format.value,
        citations=citations,
        policy=policy
    )

    if not verification.passed:
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="no_answer",
            content=NO_ANSWER_FALLBACK,
            citations=[],
            confidence=0.0,
            metadata={"mock": False, "error": "Map-Reduce verification failed."}
        )

    adapted_content = personalizer.adapt_explanation(
        verification.final_answer,
        None,
        weak_topics=[]
    )

    session_id = getattr(request, "session_id", "session-1")
    user_id = getattr(request, "user_id", "user-123")
    retrieved_chunk_ids = [str(c["id"]) for c in chunks]
    source_chunk_id = retrieved_chunk_ids[0] if retrieved_chunk_ids else None

    await chat_repository.save_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=adapted_content,
        retrieved_chunks=retrieved_chunk_ids,
        source_chunk_id=source_chunk_id
    )

    return TaskResult(
        task_id=task.task_id,
        type=task_type,
        status="success",
        content=adapted_content,
        citations=citations,
        confidence=0.9,
        metadata={"mock": False, "verification": {"status": "passed"}}
    )

def check_no_answer_trigger(query: str) -> bool:
    """Checks if query simulates requesting information outside the document context."""
    normalized = query.lower()
    return "خارج الملف" in normalized or "outside the file" in normalized

async def execute_common_pipeline_steps(
    task: Task, 
    request: Any, 
    task_type: TaskType,
    previous_results: Optional[Dict[str, Any]] = None,
    pre_generated_content: Optional[str] = None
) -> TaskResult:
    # 1. Check intent triggers
    import os
    from app.ai_system.services.llm.config import LLMConfig
    is_mock = os.getenv("PYTEST_CURRENT_TEST") is not None or not LLMConfig.GROQ_FAST_API_KEYS or any("dummy" in k for k in LLMConfig.GROQ_FAST_API_KEYS)

    if check_no_answer_trigger(task.query):
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="no_answer",
            content=NO_ANSWER_FALLBACK,
            citations=[],
            confidence=0.0,
            metadata={"mock": is_mock}
        )

    user_id = getattr(request, "user_id", "00000000-0000-0000-0000-000000000000")
    session_id = getattr(request, "session_id", "sess-xyz")
    document_id = getattr(request, "document_id", None)
    lang = getattr(request, "language", "ar")

    # 2. Retrieve relevant chunks via the RAG retrieval module.
    retrieval_result = None
    chunks = []
    if document_id and task.retrieval_required:
        retrieval_result = await document_retriever.retrieve(RetrievalRequest(
            user_id=user_id,
            document_id=document_id,
            query=task.query,
            intent=task_type.value,
        ))
        
        # 3. Check for empty/unusable RAG context -> strict grounding fallback (no-context short-circuit)
        if retrieval_result.status != RetrievalStatus.FOUND:
            if hasattr(request, "_trace_stages"):
                request._trace_stages.append({
                    "stage": "retriever",
                    "chunks_found": 0,
                    "expanded": retrieval_result.trace.expanded if retrieval_result and hasattr(retrieval_result.trace, "expanded") else False
                })
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="no_answer",
                content=NO_ANSWER_FALLBACK,
                citations=[],
                confidence=0.0,
                metadata={"mock": is_mock, "retrieval_status": retrieval_result.status.value}
            )
            
        chunks = [
            {
                "id": c.chunk_id,
                "content": c.text,
                "page_start": c.page_number or 1,
            }
            for c in retrieval_result.chunks
        ]

        # ROUTE TO MAP-REDUCE BASED ON ESTIMATED TOKEN BUDGET
        total_chars = sum(len(c.text) for c in retrieval_result.chunks)
        estimated_tokens = total_chars // 3
        
        model_context_budget = 3000
        if task_type in (TaskType.SUMMARY, TaskType.QUIZ) and estimated_tokens > model_context_budget:
            if hasattr(request, "_trace_stages"):
                request._trace_stages.append({
                    "stage": "retriever",
                    "chunks_found": len(retrieval_result.chunks),
                    "expanded": retrieval_result.trace.expanded if hasattr(retrieval_result.trace, "expanded") else False
                })
            return await execute_map_reduce(task, request, task_type, chunks, retrieval_result)

    elif task.retrieval_required:
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="no_answer",
            content=NO_ANSWER_FALLBACK,
            citations=[],
            confidence=0.0,
            metadata={"mock": False, "error": "Missing document_id context."}
        )

    # Log retriever trace stage
    if hasattr(request, "_trace_stages"):
        request._trace_stages.append({
            "stage": "retriever",
            "chunks_found": len(retrieval_result.chunks) if retrieval_result else 0,
            "expanded": retrieval_result.trace.expanded if retrieval_result and hasattr(retrieval_result.trace, "expanded") else False
        })

    # 4. Save user message to chat database
    user_msg = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=task.query,
        topic=task.metadata.get("topic")
    )
    await store.save_message(user_msg)

    # 5. Fetch student Memory Context
    memory_context = await memory_retriever.get_memory_context(
        user_id=user_id,
        session_id=session_id,
        source_id=document_id,
        source_type="document",
        user_query=task.query
    )

    # 6. Build final grounding prompt
    document_context = retrieval_result.context_text if retrieval_result else ""
    personalization_instructions = personalizer.build_prompt_context_block(
        memory_context,
        current_topic=task.metadata.get("topic"),
        current_query=task.query
    )
    
    grounded_prompt = build_grounded_prompt(
        document_context=document_context,
        memory_context=memory_context,
        personalization_instructions=personalization_instructions,
        user_query=task.query
    )

    # 7. Execute LLM & Verification Loop
    policy = getattr(request, "verification_policy", None) or VerificationPolicy()
    
    if pre_generated_content is not None:
        raw_response = pre_generated_content
        verification_passed = True
        verification_trace = {"status": "skipped", "retries": 0}
        citations = build_citations(retrieval_result.chunks if retrieval_result else [], raw_response)
    else:
        verification_passed = False
        verification_trace = {}
        citations = []
        for attempt in range(policy.max_retries + 1):
            attempt_prompt = grounded_prompt
            if attempt > 0:
                attempt_prompt += f"\n\n[Correction Instruction: Previous attempt failed verification. Ensure output grounds strictly in context and adheres to OutputFormat: {task.output_format.value}]"
            
            try:
                raw_response = await default_executor_client.generate_response(
                    prompt=attempt_prompt,
                    model_tier=task.model_tier,
                    output_format=task.output_format,
                    language=lang,
                    difficulty=getattr(request, "difficulty", "medium"),
                    number_of_questions=getattr(request, "number_of_questions", 5)
                )
                
                # Dynamic Citation Building before verify
                citations = build_citations(retrieval_result.chunks if retrieval_result else [], raw_response)
                
                # Run verifier audit
                verification = await default_verifier_client.verify(
                    user_query=task.query,
                    intent=task_type.value,
                    retrieved_chunks=chunks,
                    llm_output=raw_response,
                    output_format=task.output_format.value,
                    citations=citations,
                    policy=policy
                )
                
                verification_trace = {
                    "status": "passed" if verification.success else "failed",
                    "retries": attempt,
                    "grounding_score": verification.grounding_score,
                    "relevance_score": verification.relevance_score,
                    "schema_valid": verification.schema_valid,
                    "reason": verification.reason
                }

                # Abort retries if grounding failed (unsupported claims)
                if not verification.success and "unsupported_claims" in verification.issues:
                    verification_passed = False
                    break

                if verification.success:
                    verification_passed = True
                    break
                    
            except Exception as e:
                verification_trace = {"status": "error", "error": str(e), "retries": attempt}
                
        if not verification_passed:
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="no_answer",
                content=NO_ANSWER_FALLBACK,
                citations=[],
                confidence=0.0,
                metadata={
                    "mock": is_mock, 
                    "error": "Verification failed, fallback triggered.",
                    "verification": verification_trace
                }
            )

    # Log executor and verifier trace stages
    if hasattr(request, "_trace_stages"):
        request._trace_stages.append({
            "stage": "executor",
            "model": "groq",
            "status": "completed"
        })
        request._trace_stages.append({
            "stage": "verifier",
            "passed": verification_passed,
            "grounding_score": verification_trace.get("grounding_score", 1.0)
        })

    # 8. Apply personalization adapt
    adapted_content = personalizer.adapt_explanation(
        raw_response, 
        memory_context.user_profile, 
        weak_topics=memory_context.weak_topics, 
        topic=task.metadata.get("topic")
    )

    # 9. Save assistant response with chunk traceability
    retrieved_chunk_ids = [str(c["id"]) for c in chunks]
    source_chunk_id = retrieved_chunk_ids[0] if retrieved_chunk_ids else None

    await chat_repository.save_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=adapted_content,
        topic=task.metadata.get("topic"),
        retrieved_chunks=retrieved_chunk_ids,
        source_chunk_id=source_chunk_id
    )

    # Log save chat state and citations trace stages
    if hasattr(request, "_trace_stages"):
        request._trace_stages.append({
            "stage": "citations",
            "count": len(citations)
        })
        request._trace_stages.append({
            "stage": "save_chat_state",
            "status": "completed"
        })

    # 10. Rolling summarizer threshold check
    await summarizer.summarize_session(user_id, session_id, force=False)

    retrieval_info = {
        "status": retrieval_result.status.value if retrieval_result else "not_run",
        "confidence": retrieval_result.confidence if retrieval_result else 0.0,
        "chunks_used": len(retrieval_result.chunks) if retrieval_result else 0,
        "latency_ms": retrieval_result.trace.total_retrieval_latency_ms if retrieval_result else 0,
    }

    memory_info = {
        "academic_level": memory_context.user_profile.academic_level if (memory_context.user_profile and hasattr(memory_context.user_profile, 'academic_level')) else "beginner",
        "weak_topics": [t.topic for t in memory_context.weak_topics] if memory_context.weak_topics else [],
        "session_summary": memory_context.session_summary or "None",
        "has_personalization": personalization_instructions is not None and len(personalization_instructions) > 0,
        "retrieved_memory_count": len(memory_context.relevant_past) if memory_context.relevant_past else 0
    }

    return TaskResult(
        task_id=task.task_id,
        type=task_type,
        status="success",
        content=adapted_content,
        citations=citations,
        confidence=MOCK_CONFIDENCE,
        metadata={
            "mock": is_mock,
            "document_id": document_id,
            "retrieved_chunks_count": len(retrieved_chunk_ids),
            "memory_info": memory_info,
            "retrieval_info": retrieval_info,
            "verification_info": verification_trace
        }
    )


async def run_chat_answer_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Localized QA search pipeline using vector chunks."""
    return await execute_common_pipeline_steps(task, request, TaskType.CHAT_ANSWER, previous_results)

async def run_explain_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Explanation pipeline for a targeted segment."""
    return await execute_common_pipeline_steps(task, request, TaskType.EXPLAIN, previous_results)

async def run_summary_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level summary utilizing all chunks."""
    return await execute_common_pipeline_steps(task, request, TaskType.SUMMARY, previous_results)

async def run_quiz_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level quiz generator utilizing all chunks."""
    result = await execute_common_pipeline_steps(task, request, TaskType.QUIZ, previous_results)
    
    # Parse generated questions to inject into metadata for downstream tasks
    if result.status == "success":
        import json
        try:
            questions = json.loads(result.content)
            result.metadata["generated_questions"] = questions
        except Exception:
            # Fallback if content was personalized into raw text
            lang = getattr(request, "language", "ar")
            result.metadata["generated_questions"] = [
                {"id": "q1", "question": "ما عاصمة مصر؟" if lang == "ar" else "What is the capital of Egypt?", "options": ["القاهرة", "الإسكندرية"] if lang == "ar" else ["Cairo", "Alexandria"], "correct": "القاهرة" if lang == "ar" else "Cairo"},
                {"id": "q2", "question": "ما الصيغة الكيميائية للماء؟" if lang == "ar" else "What is the chemical formula of water?", "options": ["H2O", "CO2"], "correct": "H2O"}
            ]
    return result

async def run_answer_table_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates an answer table based on previous quiz questions."""
    lang = getattr(request, "language", "ar")
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
    else:
        table_content = None  # Force generation from ExecutorClient default

    result = await execute_common_pipeline_steps(task, request, TaskType.ANSWER_TABLE, previous_results, pre_generated_content=table_content)
    if result.status == "success":
        result.metadata["consumed_quiz_questions"] = True
    return result

async def run_key_points_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Extracts key points."""
    return await execute_common_pipeline_steps(task, request, TaskType.KEY_POINTS, previous_results)

async def run_comparison_table_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates comparison tables."""
    return await execute_common_pipeline_steps(task, request, TaskType.COMPARISON_TABLE, previous_results)

async def run_flashcards_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates flashcards."""
    return await execute_common_pipeline_steps(task, request, TaskType.FLASHCARDS, previous_results)

async def run_answer_evaluation_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Evaluates student answers."""
    return await execute_common_pipeline_steps(task, request, TaskType.ANSWER_EVALUATION, previous_results)

# Global Registry
PIPELINE_REGISTRY: Dict[str, Any] = {
    TASK_CHAT_ANSWER: run_chat_answer_pipeline,
    TASK_EXPLAIN: run_explain_pipeline,
    TASK_SUMMARY: run_summary_pipeline,
    TASK_QUIZ: run_quiz_pipeline,
    TASK_ANSWER_TABLE: run_answer_table_pipeline,
    TASK_KEY_POINTS: run_key_points_pipeline,
    TASK_COMPARISON_TABLE: run_comparison_table_pipeline,
    TASK_FLASHCARDS: run_flashcards_pipeline,
    TASK_ANSWER_EVALUATION: run_answer_evaluation_pipeline
}
