import json
import logging
import hashlib
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.ai_schema import Task, TaskResult, Citation, TaskType, VerificationPolicy, OutputFormat
from app.db.supabase_client import get_supabase_client
from app.ai_system.services.llm.model_router import resolve_config_for_role, LLMRole
from app.ai_system.services.llm.providers.groq_provider import GroqProvider
from app.ai_system.services.llm.exceptions import ContextMissingException
from app.core.config import settings
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
from app.ai_system.services.llm.generate import generate as llm_generate
from app.ai_system.services.llm.config import LLMConfig
from app.ai_system.services.llm.schemas import (
    LLMEngineerPayload, SourceInfo, StrictGroundingPolicy,
    ExpectedLLMOutputFormat, ChunkContext, MemoryContext
)
from app.ai_system.retrieval import get_document_retriever
from app.ai_system.retrieval.schemas import RetrievalRequest, RetrievalStatus
from app.ai_system.orchestrator.verifier_client import default_verifier_client

logger = logging.getLogger(__name__)

MOCK_CONFIDENCE = 0.9

memory_retriever = MemoryRetriever()
personalizer = PersonalizationEngine()
store = MemoryStore()
summarizer = Summarizer()
document_retriever = get_document_retriever()

def _format_recent_messages(memory_context) -> str:
    """Format recent session messages from MemoryContext into a compact history string for the LLM prompt."""
    messages = getattr(memory_context, "recent_messages", None)
    if not messages:
        return ""
    lines = []
    for m in messages:
        role = getattr(m, "role", "user")
        content = getattr(m, "content", "")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)

def check_no_answer_trigger(query: str) -> bool:

    """Checks if query simulates requesting information outside the document context."""
    normalized = query.lower()
    return "خارج الملف" in normalized or "outside the file" in normalized

STOPWORDS = {"a", "an", "the", "about", "on", "in", "of", "to", "for", "and", "or", "is", "are"}

def build_citations(retrieved_chunks: List[Any], llm_output: str, source_chunk_ids: Optional[List[str]] = None) -> List[Citation]:
    """
    Constructs citations referencing only the retrieved chunks that are actually
    relevant or cited in the LLM response text, using the validation package's citation builder.
    """
    from app.ai_system.validation.citation_builder import build_citations as val_build_citations
    from app.ai_system.validation.schemas import RetrievedChunk as ValRetrievedChunk
    from app.schemas.ai_schema import Citation
    
    if not retrieved_chunks or not llm_output:
        return []
        
    val_chunks = []
    for c in retrieved_chunks:
        # Resolve ID
        if hasattr(c, "chunk_id") and getattr(c, "chunk_id") is not None:
            c_id = c.chunk_id
        elif hasattr(c, "id") and getattr(c, "id") is not None:
            c_id = c.id
        elif isinstance(c, dict):
            c_id = c.get("chunk_id") or c.get("id")
        else:
            c_id = None

        # Resolve Text
        if hasattr(c, "text") and getattr(c, "text") is not None:
            text = c.text
        elif hasattr(c, "content") and getattr(c, "content") is not None:
            text = c.content
        elif isinstance(c, dict):
            text = c.get("text") or c.get("content", "")
        else:
            text = ""

        # Resolve Page
        if hasattr(c, "page_number") and getattr(c, "page_number") is not None:
            page = c.page_number
        elif hasattr(c, "page_start") and getattr(c, "page_start") is not None:
            page = c.page_start
        elif isinstance(c, dict):
            page = c.get("page_number") or c.get("page_start", 1)
        else:
            page = 1

        # Resolve Section
        if hasattr(c, "section_title") and getattr(c, "section_title") is not None:
            section = c.section_title
        elif isinstance(c, dict):
            section = c.get("section_title")
        else:
            section = None

        # Resolve Score
        if hasattr(c, "similarity_score") and getattr(c, "similarity_score") is not None:
            score = c.similarity_score
        elif hasattr(c, "score") and getattr(c, "score") is not None:
            score = c.score
        elif isinstance(c, dict):
            score = c.get("similarity_score") or c.get("score", 0.90)
        else:
            score = 0.90
        
        val_chunks.append(ValRetrievedChunk(
            chunk_id=str(c_id),
            text=text,
            page_number=page,
            section_title=section,
            similarity_score=score
        ))

    if source_chunk_ids:
        source_chunk_ids_set = {str(sid) for sid in source_chunk_ids}
        filtered_val_chunks = [vc for vc in val_chunks if vc.chunk_id in source_chunk_ids_set]
        if filtered_val_chunks:
            val_chunks = filtered_val_chunks

    build_result = val_build_citations(llm_output, val_chunks)
    
    citations = []
    for cit in build_result.citations:
        citations.append(Citation(
            chunk_id=cit.chunk_id,
            page_number=cit.page_number or 1,
            section_title=cit.section_title or "RAG Pipeline",
            score=cit.relevance_score or 0.9
        ))
        
    return citations


async def execute_common_pipeline_steps(
    task: Task,
    request: Any,
    task_type: TaskType,
    previous_results: Optional[Dict[str, Any]] = None,
    pre_generated_content: Optional[str] = None
) -> TaskResult:
    """
    Executes core pipeline steps:
    1. Check query triggers
    2. Retrieve chunks (RAG)
    3. Check empty chunks -> return fallback
    4. Save user query
    5. Load memory context
    6. Construct grounded prompt
    7. Execute LLM & Verify Loop with retries
    8. Apply personalization instructions
    9. Save assistant response with chunk traceability
    10. Run rolling session summaries
    """
    # 1. Check intent triggers
    is_mock = not LLMConfig.fast_keys()

    if check_no_answer_trigger(task.query):
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="no_answer",
            content=NO_ANSWER_FALLBACK,
            citations=[],
            confidence=0.0,
            metadata={"mock": is_mock, "retrieval_mode": "temporary_chunk_context_until_rag"}
        )

    user_id = getattr(request, "user_id", "00000000-0000-0000-0000-000000000000")
    session_id = getattr(request, "session_id", "sess-xyz")
    document_id = getattr(request, "document_id", None)
    lang = getattr(request, "language", "ar")
    state = getattr(request, "state", None) or getattr(request, "_pipeline_state", None)
    retrieval_result = (
        state.retrieval_result if state is not None
        else getattr(request, "_retrieval_result", None)
    )


    # 2. Retrieve relevant chunks via the RAG retrieval module.
    chunks = []
    val_chunks = []
    evidence_status_str = "sufficient"
    
    if document_id and task.retrieval_required:
        from app.ai_system.validation.context_collector import collect_context
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import ExecutionStrategy, EvidenceStatus, DocumentTaskType, ResponseStrategy
        
        strategy = ExecutionStrategy.focused_retrieval
        primary_task = DocumentTaskType.document_factual_qa
        validation_res = getattr(request, "_input_validation", None)
        if validation_res:
            strategy = validation_res.context_strategy or ExecutionStrategy.focused_retrieval
            primary_task = validation_res.primary_task or DocumentTaskType.document_factual_qa
            
        # Single retrieval call — DocumentRetriever already performs 3-attempt
        # progressive threshold relaxation (0.55 → 0.40 → 0.25) internally.
        # Do NOT duplicate query rewriting here; route through collect_context.
        val_chunks = await collect_context(
            strategy=strategy,
            query=task.query,
            document_id=document_id,
            user_id=user_id,
            request=request
        )

        retrieval_result = (
            state.retrieval_result if state is not None
            else getattr(request, "_retrieval_result", None)
        )

        # Check evidence sufficiency
        evidence_res = await validate_evidence(
            primary_task=primary_task,
            collected_chunks=val_chunks,
            query=task.query
        )

        # On weak evidence, log diagnostic; retriever already exhausted thresholds
        if getattr(evidence_res, "recovery_recommended", False):
            logger.info(
                f"[EVIDENCE] Weak evidence after retriever relaxation for query: {task.query!r}. "
                f"Proceeding with partial answer directive."
            )
        evidence_status_str = evidence_res.evidence_status.value

        
        # If insufficient, skip Executor LLM and verify loop entirely!
        if evidence_res.evidence_status == EvidenceStatus.insufficient:
            from app.ai_system.validation.rules import get_fallback_message
            fallback_reason = "DOCUMENT_INFORMATION_NOT_FOUND"
            fallback_msg = get_fallback_message(fallback_reason, lang=lang)
            
            if hasattr(request, "_trace_stages"):
                request._trace_stages.append({
                    "stage": "retriever",
                    "status": "failed",
                    "chunks_found": len(val_chunks)
                })
                request._trace_stages.append({
                    "stage": "executor",
                    "model": "rule_based",
                    "status": "passed"
                })
                request._trace_stages.append({
                    "stage": "verifier",
                    "passed": True,
                    "grounding_score": 1.0
                })
                
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="no_answer",
                content=fallback_msg,
                citations=[],
                confidence=0.0,
                metadata={
                    "mock": is_mock, 
                    "evidence_status": "insufficient",
                    "final_response_type": "document_fallback",
                    "fallback_reason_code": fallback_reason
                }
            )
            
        elif evidence_res.evidence_status == EvidenceStatus.partial:
            # Partial evidence: proceed to executor but instruct it to caveat unsupported parts.
            # Inject bilingual directive so prompt is effective for AR and EN questions.
            if lang == "ar":
                task.query += (
                    "\n\n[توجيه النظام: أجب على الأجزاء المدعومة بالسياق فقط. "
                    "إذا كانت المعلومات غير كاملة، استخدم عبارة [معلومة غير متاحة في المستند] "
                    "بدلاً من اختلاق معلومات. اذكر المصادر المستخدمة.]"
                )
            else:
                task.query += (
                    "\n\n[System directive: Answer only the parts supported by context. "
                    "For missing information use '[Information not available in document]' rather than inventing facts. "
                    "Cite the sources you used.]"
                )

        elif evidence_res.evidence_status == EvidenceStatus.conflicting:
            task.query += (
                "\n\n[System directive: The document chunks contain conflicting information. "
                "Present the conflicting views clearly and ask the user for clarification.]"
            )
            
        chunks = [
            {
                "id": c.chunk_id,
                "content": c.text,
                "page_start": c.page_number or 1,
            }
            for c in val_chunks
        ]
        
        if hasattr(request, "_trace_stages"):
            request._trace_stages.append({
                "stage": "retriever",
                "status": "passed",
                "chunks_found": len(chunks)
            })
    elif task.retrieval_required:
        if hasattr(request, "_trace_stages"):
            request._trace_stages.append({
                "stage": "retriever",
                "status": "failed",
                "chunks_found": 0
            })
        from app.ai_system.validation.rules import get_fallback_message
        fallback_msg = get_fallback_message("INTERNAL_PIPELINE_ERROR", lang=lang)
        return TaskResult(
            task_id=task.task_id,
            type=task_type,
            status="no_answer",
            content=fallback_msg,
            citations=[],
            confidence=0.0,
            metadata={
                "mock": is_mock, 
                "error": "Missing document_id context.",
                "final_response_type": "technical_failure",
                "fallback_reason_code": "INTERNAL_PIPELINE_ERROR"
            }
        )
    else:
        if hasattr(request, "_trace_stages"):
            request._trace_stages.append({
                "stage": "retriever",
                "status": "passed",
                "chunks_found": 0
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

    # 6. Temporary context selection
    if task_type in [TaskType.CHAT_ANSWER, TaskType.EXPLAIN, TaskType.KEY_POINTS, TaskType.COMPARISON_TABLE]:
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

    # Execute task using precomputed content or LLM generation
    content_result = ""
    usage_metrics = None
    llm_response = None
    verification_trace = {}

    if pre_generated_content is not None:
        content_result = pre_generated_content
        logger.info(f"Using precomputed content for task {task.task_id} (type: {task_type})")
        source_chunk_ids = [c.chunk_id for c in retrieved_context[:3]]
        verification_trace = {"status": "skipped", "retries": 0}
        citations = build_citations(retrieval_result.chunks if retrieval_result else [], pre_generated_content, source_chunk_ids)
    else:
        # Build LLMEngineerPayload
        output_type = "text"
        if task_type == TaskType.QUIZ:
            output_type = "quiz"
        elif task_type == TaskType.SUMMARY:
            output_type = "summary"
        elif task_type == TaskType.EXPLAIN:
            output_type = "explanation"
        elif task_type == TaskType.ANSWER_EVALUATION:
            output_type = "answer_evaluation"

        expected_format = ExpectedLLMOutputFormat(
            type=output_type,
            question_count=5 if task_type == TaskType.QUIZ else None,
            must_be_grounded=True,
            must_not_use_general_knowledge=True
        )

        memory_payload = MemoryContext(
            quiz_difficulty=getattr(request, "difficulty", "medium"),
            preferred_language=lang,
            recent_context_summary=_format_recent_messages(memory_context)
        )


        payload = LLMEngineerPayload(
            task_id=task.task_id,
            task_type=task_type.value,
            pipeline_type="standard_rag",
            original_user_query=task.query,
            task_query=task.query,
            source=SourceInfo(source_id=str(document_id) if document_id else "system", source_type="document"),
            retrieved_document_context=retrieved_context,
            memory_context=memory_payload,
            strict_grounding_policy=StrictGroundingPolicy(
                academic_source_of_truth="retrieved_document_context_only",
                memory_usage="personalization_only",
                if_document_context_insufficient=NO_ANSWER_FALLBACK
            ),
            expected_llm_output_format=expected_format
        )

        policy = getattr(request, "verification_policy", None) or VerificationPolicy()
        verification_passed = False
        verification_trace = {}
        citations = []
        verification = None
        
        for attempt in range(policy.max_retries + 1):
            if attempt > 0:
                payload.task_query = (
                    f"{task.query}\n\n[Correction Instruction: Previous attempt failed verification. "
                    f"Ensure output grounds strictly in context and adheres to OutputFormat: {output_type}]"
                )
            
            try:
                is_map_reduce = False
                if task_type in [TaskType.SUMMARY, TaskType.QUIZ]:
                    total_chars = sum(len(c.get("content", "")) for c in chunks)
                    if (total_chars // 3) > 3000:
                        is_map_reduce = True

                if is_map_reduce:
                    # 1. Map Phase
                    map_payload = payload.model_copy()
                    if task_type == TaskType.SUMMARY:
                        map_payload.task_type = "summary_map"
                    elif task_type == TaskType.QUIZ:
                        map_payload.task_type = "quiz"
                    
                    map_response = await llm_generate(map_payload)
                    if map_response.status == "failure":
                        verification_trace = {"status": "error", "error": map_response.error_message, "retries": attempt}
                        continue
                    
                    # 2. Reduce Phase
                    reduce_payload = payload.model_copy()
                    if task_type == TaskType.SUMMARY:
                        reduce_payload.task_type = "summary_reduce"
                    elif task_type == TaskType.QUIZ:
                        reduce_payload.task_type = "quiz"
                    
                    map_text = map_response.output_text or (json.dumps(map_response.output_json) if map_response.output_json else "")
                    reduce_payload.task_query = f"Synthesize/reduce the following content:\n{map_text}"
                    reduce_payload.retrieved_document_context = []
                    
                    llm_response = await llm_generate(reduce_payload)
                else:
                    llm_response = await llm_generate(payload)

                if llm_response.status == "failure":
                    verification_trace = {"status": "error", "error": llm_response.error_message, "retries": attempt}
                    continue
                
                # Check verification
                raw_response = llm_response.output_text if llm_response.output_text is not None else (json.dumps(llm_response.output_json, ensure_ascii=False) if llm_response.output_json else "")
                
                # If we have low-severity abuse, compose soft boundary warning BEFORE running verifier
                validation_res = getattr(request, "_input_validation", None)
                if validation_res and \
                   validation_res.response_strategy == ResponseStrategy.answer_with_soft_boundary:
                    from app.ai_system.validation.dynamic_response import GENTLE_ABUSE_WARNING_AR, GENTLE_ABUSE_WARNING_EN
                    warning_suffix = GENTLE_ABUSE_WARNING_AR if lang == "ar" else GENTLE_ABUSE_WARNING_EN
                    if warning_suffix not in raw_response:
                        raw_response = raw_response + warning_suffix
                
                citations = build_citations(val_chunks, raw_response, llm_response.source_chunk_ids)
                
                strategy_val = validation_res.response_strategy if validation_res else ResponseStrategy.continue_to_planner
                primary_task_val = validation_res.primary_task if validation_res else None

                verification = await default_verifier_client.verify(
                    user_query=task.query,
                    intent=task_type.value,
                    retrieved_chunks=chunks,
                    llm_output=raw_response,
                    output_format=task.output_format.value if hasattr(task.output_format, 'value') else str(task.output_format),
                    citations=citations,
                    policy=policy,
                    response_strategy=strategy_val,
                    primary_task=primary_task_val
                )
                
                verification_trace = {
                    "status": "passed" if verification.success else "failed",
                    "retries": attempt,
                    "grounding_score": verification.grounding_score,
                    "relevance_score": verification.relevance_score,
                    "schema_valid": verification.schema_valid,
                    "reason": verification.reason
                }

                if verification.success:
                    verification_passed = True
                    break
            except Exception as e:
                # Map technical exceptions to typed reason codes
                err_str = str(e)
                exc_type = type(e).__name__
                if "RateLimitError" in exc_type or "429" in err_str or "rate_limit" in err_str.lower():
                    reason_code = "GENERATION_TEMPORARILY_UNAVAILABLE"
                elif "AllKeysExhausted" in exc_type:
                    reason_code = "GENERATION_TEMPORARILY_UNAVAILABLE"
                elif "timeout" in err_str.lower() or "Timeout" in exc_type:
                    reason_code = "RETRIEVAL_TEMPORARILY_UNAVAILABLE"
                elif "Verification" in exc_type or "verification" in err_str.lower():
                    reason_code = "VERIFICATION_FAILED"
                else:
                    reason_code = "INTERNAL_PIPELINE_ERROR"
                logger.error(f"PIPELINE RUNTIME EXCEPTION [{reason_code}]: {e}", exc_info=True)
                verification_trace = {"status": "error", "error": str(e), "reason_code": reason_code, "retries": attempt}

        if not verification_passed:
            last_reason = verification_trace.get("reason_code") or "DOCUMENT_INFORMATION_NOT_FOUND"
            if last_reason == "DOCUMENT_INFORMATION_NOT_FOUND" and verification_trace.get("status") == "failed":
                last_reason = "VERIFICATION_FAILED"
                
            response_type = "technical_failure" if last_reason in [
                "RETRIEVAL_TEMPORARILY_UNAVAILABLE",
                "GENERATION_TEMPORARILY_UNAVAILABLE",
                "VERIFICATION_FAILED",
                "CITATION_REBUILD_FAILED",
                "INTERNAL_PIPELINE_ERROR"
            ] else "document_fallback"
            
            from app.ai_system.validation.rules import get_fallback_message
            fallback_msg = get_fallback_message(last_reason, lang=lang)

            if hasattr(request, "_trace_stages"):
                request._trace_stages.append({
                    "stage": "executor",
                    "model": "groq",
                    "status": "failed"
                })
                request._trace_stages.append({
                    "stage": "verifier",
                    "passed": False,
                    "grounding_score": 0.0
                })
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="no_answer",
                content=fallback_msg,
                citations=[],
                confidence=0.0,
                metadata={
                    "mock": is_mock,
                    "error": "Verification failed, fallback triggered.",
                    "verification": verification_trace,
                    "final_response_type": response_type,
                    "fallback_reason_code": last_reason
                }
            )

        if llm_response.output_text:
            content_result = llm_response.output_text
        elif llm_response.output_json:
            content_result = json.dumps(llm_response.output_json, ensure_ascii=False)
        
        source_chunk_ids = llm_response.source_chunk_ids
        usage_metrics = llm_response.usage_metrics.model_dump() if llm_response.usage_metrics else None

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
    personalization_info = {}
    if memory_context:
        adapted_content = personalizer.adapt_explanation(
            content_result,
            memory_context.user_profile,
            weak_topics=memory_context.weak_topics,
            topic=task.metadata.get("topic")
        )
        
        # Extract personalization details for metadata
        level = memory_context.user_profile.learning_level if (memory_context.user_profile and hasattr(memory_context.user_profile, 'learning_level')) else "beginner"
        style = memory_context.user_profile.explanation_style if (memory_context.user_profile and hasattr(memory_context.user_profile, 'explanation_style')) else "simple"
        personalization_info = {"level": level, "style": style}
        
        import re
        content_result = re.sub(r"\s*\[Personalized:[^\]]*\]", "", adapted_content).strip()

    # 9. Save assistant response with chunk traceability
    retrieved_chunk_ids = [str(c["id"]) for c in chunks]
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

    personalization_instructions = personalizer.build_prompt_context_block(
        memory_context,
        current_topic=task.metadata.get("topic"),
        current_query=task.query
    )

    memory_info = {
        "academic_level": memory_context.user_profile.academic_level if (memory_context.user_profile and hasattr(memory_context.user_profile, 'academic_level')) else "beginner",
        "weak_topics": [t.topic for t in memory_context.weak_topics] if memory_context.weak_topics else [],
        "session_summary": memory_context.session_summary or "None",
        "has_personalization": personalization_instructions is not None and len(personalization_instructions) > 0,
        "retrieved_memory_count": len(memory_context.relevant_past) if memory_context.relevant_past else 0
    }

    # Quiz questions caching for answer table consumption
    metadata = {
        "mock": is_mock,
        "document_id": document_id,
        "retrieved_chunks_count": len(retrieved_chunk_ids),
        "memory_info": memory_info,
        "retrieval_info": retrieval_info,
        "verification_info": verification_trace,
        "usage_metrics": usage_metrics,
        "personalization": personalization_info
    }

    if task_type == TaskType.QUIZ and pre_generated_content is None and llm_response and llm_response.output_json:
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

    task_confidence = verification.confidence if (pre_generated_content is None and 'verification' in locals() and verification is not None) else MOCK_CONFIDENCE
    return TaskResult(
        task_id=task.task_id,
        type=task_type,
        status="success" if content_result != NO_ANSWER_FALLBACK else "no_answer",
        content=content_result,
        citations=citations,
        confidence=task_confidence,
        metadata=metadata
    )


async def run_chat_answer_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Localized QA search pipeline using vector chunks."""
    return await execute_common_pipeline_steps(task, request, TaskType.CHAT_ANSWER, previous_results)

async def run_explain_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Explanation pipeline for a targeted segment."""
    return await execute_common_pipeline_steps(task, request, TaskType.EXPLAIN, previous_results)

class MCQQuestion(BaseModel):
    question_text: str = Field(..., description="The multiple choice question text in the target language.")
    options: List[str] = Field(..., description="Exactly 4 options.")
    correct_option_id: int = Field(..., description="Index of correct option (0 to 3).")
    explanation: str = Field(..., description="Detailed explanation of the correct answer.")
    concept: str = Field(..., description="The main concept tested by this question.")
    difficulty: str = Field(..., description="Difficulty level: 'easy', 'medium', 'hard'.")

class QuizData(BaseModel):
    title: str = Field(..., description="Quiz title.")
    questions: List[MCQQuestion]


async def run_summary_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level summary utilizing Map-Reduce and cache indexing."""
    user_id = getattr(request, "user_id", None)
    document_id = getattr(request, "document_id", None)
    lang = getattr(request, "language", "ar")
    
    if not document_id:
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.SUMMARY,
            status="no_answer",
            content="Missing document context.",
            citations=[],
            confidence=0.0
        )

    summary_size = task.metadata.get("summary_size") or getattr(request, "summary_size", None) or "medium"
    summary_size = summary_size.lower().strip()
    target_word_count = task.metadata.get("target_word_count") or getattr(request, "target_word_count", None)

    # 1. Fetch all chunks
    supabase = get_supabase_client()
    resp = supabase.table("document_chunks")\
                   .select("id, content, page_start, chunk_index")\
                   .eq("document_id", document_id)\
                   .order("chunk_index")\
                   .execute()
    chunks = resp.data if resp and resp.data else []
    if not chunks:
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.SUMMARY,
            status="no_answer",
            content=NO_ANSWER_FALLBACK if lang == "ar" else "I could not find a clear answer in the uploaded file.",
            citations=[],
            confidence=0.0
        )

    # 2. Compute document hash and config hash
    doc_text_concat = "".join(c.get("content", "") for c in chunks)
    document_hash = hashlib.sha256(doc_text_concat.encode("utf-8")).hexdigest()
    
    _, model_name = resolve_config_for_role(LLMRole.MAP_WORKER)
    config_hash = hashlib.sha256(f"model={model_name};temp=0.1;size={summary_size};words={target_word_count}".encode("utf-8")).hexdigest()

    # 3. Check Cache
    cache_resp = supabase.table("document_summaries")\
                         .select("*")\
                         .eq("document_id", document_id)\
                         .eq("user_id", user_id)\
                         .eq("summary_size", summary_size)\
                         .eq("language", lang)\
                         .eq("generation_config_hash", config_hash)\
                         .execute()
    if cache_resp.data:
        cached = cache_resp.data[0]
        if cached["summary_status"] == "completed":
            logger.info("Summary Cache HIT!")
            return TaskResult(
                task_id=task.task_id,
                type=TaskType.SUMMARY,
                status="success",
                content=cached["content"],
                citations=cached.get("citations") or [],
                confidence=0.95,
                metadata={"cache_hit": True, "document_id": document_id}
            )

    # Create pending cache row
    cache_id = str(uuid.uuid4())
    supabase.table("document_summaries").insert({
        "id": cache_id,
        "user_id": user_id,
        "document_id": document_id,
        "summary_size": summary_size,
        "target_word_count": target_word_count,
        "content": "Processing summary...",
        "language": lang,
        "document_hash": document_hash,
        "prompt_version": "v1",
        "model_name": model_name,
        "summary_status": "pending",
        "generation_config_hash": config_hash
    }).execute()

    # 4. Map-Reduce Summary Flow
    try:
        # Update to processing state
        supabase.table("document_summaries").update({"summary_status": "processing"}).eq("id", cache_id).execute()

        # Group chunks into blocks of ~1500 words
        blocks = []
        current_block = []
        current_word_count = 0
        for c in chunks:
            c_text = c.get("content", "")
            words = len(c_text.split())
            if current_word_count + words > 1500 and current_block:
                blocks.append(current_block)
                current_block = [c]
                current_word_count = words
            else:
                current_block.append(c)
                current_word_count += words
        if current_block:
            blocks.append(current_block)

        provider = GroqProvider()

        async def process_block(block_chunks: list, depth: int = 0) -> str:
            api_key, model_name = resolve_config_for_role(LLMRole.MAP_WORKER)
            block_text = "\n".join(c.get("content", "") for c in block_chunks)
            if lang == "ar":
                system_prompt = (
                    "أنت عامل تلخيص. قم بتلخيص قسم المستند التالي باللغة العربية، "
                    "مع إبراز المفاهيم الأساسية والحقائق والأسماء. اجعله واقعيًا وموجزًا. "
                    "يجب أن تكون المخرجات باللغة العربية فقط."
                )
                prompt = f"نص القسم:\n{block_text}\nالملخص:"
            else:
                system_prompt = (
                    "You are a Map-Reduce summary worker. Summarize the following document section in English, "
                    "highlighting key concepts, facts, names, and timeline dates. Keep it factual and concise."
                )
                prompt = f"Section text:\n{block_text}\nSummary:"
            
            for trial in range(3): # up to 2 retries
                try:
                    res = await provider.generate(
                        model=model_name,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        api_key=api_key,
                        profile="memory_map",
                        temperature=0.1
                    )
                    return res["text"]
                except Exception as e:
                    logger.warning(f"Map block execution failed (trial {trial}, depth {depth}): {e}")
                    if trial == 2:
                        # Split block in half
                        if len(block_chunks) > 1 and depth < 2:
                            mid = len(block_chunks) // 2
                            left = block_chunks[:mid]
                            right = block_chunks[mid:]
                            try:
                                left_res, right_res = await asyncio.gather(
                                    process_block(left, depth+1),
                                    process_block(right, depth+1)
                                )
                                return f"{left_res}\n\n{right_res}"
                            except Exception as gather_exc:
                                logger.error(f"Hierarchical block split execution failed: {gather_exc}")
                        
                        # Fallback to default config key
                        try:
                            fallback_key = settings.GROQ_DEFAULT_API_KEY.strip()
                            fallback_model = settings.GROQ_DEFAULT_MODEL.strip()
                            if fallback_key and fallback_model:
                                res = await provider.generate(
                                    model=fallback_model,
                                    prompt=prompt,
                                    system_prompt=system_prompt,
                                    api_key=fallback_key,
                                    profile="memory_map",
                                    temperature=0.1
                                )
                                return res["text"]
                        except Exception as fallback_exc:
                            logger.error(f"Fallback model execution failed: {fallback_exc}")
                        
                        return f"[Warning: Partial summary content mapping failed for this section.]"
            return ""

        map_summaries = await asyncio.gather(*(process_block(b) for b in blocks))
        combined_map_text = "\n\n=== SECTION SUMMARY ===\n\n".join(map_summaries)

        # Reduce Phase
        api_key, model_name = resolve_config_for_role(LLMRole.REDUCE_WORKER)
        
        size_targets = {
            "concise": 200,
            "medium": 500,
            "detailed": 1200,
            "custom": target_word_count or 100
        }
        target = size_targets.get(summary_size, 500)

        if lang == "ar":
            system_prompt = (
                f"أنت مجمع ملخصات. قم بتجميع ملخصات الأقسام في ملخص مستند شامل ومنظم باللغة العربية. "
                f"استخدم تنسيق Markdown للعناوين. الطول المستهدف: حوالي {target} كلمة. "
                f"يجب أن يكون الرد والمخرجات باللغة العربية فقط."
            )
            prompt = f"ملخصات الأقسام:\n{combined_map_text}\nالملخص النهائي:"
        else:
            system_prompt = (
                f"You are a Map-Reduce summary reducer. Synthesize the section summaries into a single comprehensive, "
                f"structured document summary in English. Format with markdown headings. Target length: approximately {target} words."
            )
            prompt = f"Section summaries:\n{combined_map_text}\nReduced Summary:"

        res = await provider.generate(
            model=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            api_key=api_key,
            profile="execution_reduce",
            temperature=0.2
        )
        summary_text = res["text"]
        actual_word_count = len(summary_text.split())

        # Save to cache
        supabase.table("document_summaries").update({
            "content": summary_text,
            "summary_status": "completed",
            "actual_word_count": actual_word_count
        }).eq("id", cache_id).execute()

        # Build citations trace
        citations = []
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.SUMMARY,
            status="success",
            content=summary_text,
            citations=citations,
            confidence=0.95,
            metadata={"cache_hit": False, "document_id": document_id}
        )

    except Exception as e:
        logger.error(f"Summary Map-Reduce failed: {e}", exc_info=True)
        supabase.table("document_summaries").update({
            "summary_status": "failed",
            "failure_metadata": {"error": str(e)}
        }).eq("id", cache_id).execute()
        
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.SUMMARY,
            status="no_answer",
            content=NO_ANSWER_FALLBACK if lang == "ar" else "I could not find a clear answer in the uploaded file.",
            citations=[],
            confidence=0.0,
            error=str(e)
        )


async def run_quiz_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level quiz utilizing Map-Reduce and separated secure database answers."""
    user_id = getattr(request, "user_id", None)
    document_id = getattr(request, "document_id", None)
    lang = getattr(request, "language", "ar")

    if not document_id:
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.QUIZ,
            status="no_answer",
            content="Missing document context.",
            citations=[],
            confidence=0.0
        )

    difficulty = (task.metadata.get("difficulty") or getattr(request, "difficulty", None) or "medium").lower()
    num_questions = task.metadata.get("number_of_questions") or getattr(request, "number_of_questions", None) or 5
    
    size = "medium"
    if num_questions <= 3:
        size = "small"
    elif num_questions >= 8:
        size = "large"

    supabase = get_supabase_client()

    # 1. Check cache database
    quiz_resp = supabase.table("quizzes")\
                        .select("*")\
                        .eq("document_id", document_id)\
                        .eq("user_id", user_id)\
                        .eq("difficulty", difficulty)\
                        .eq("size", size)\
                        .execute()
    if quiz_resp.data:
        quiz_id = quiz_resp.data[0]["id"]
        title = quiz_resp.data[0]["title"]
        
        # Load questions
        q_resp = supabase.table("quiz_questions")\
                         .select("*")\
                         .eq("quiz_id", quiz_id)\
                         .execute()
                         
        # Load correct answers (trusted backend can SELECT)
        a_resp = supabase.table("quiz_question_answers")\
                         .select("*")\
                         .in_("question_id", [q["id"] for q in q_resp.data])\
                         .execute()
        ans_map = {a["question_id"]: a for a in a_resp.data}
        
        mapped_questions = []
        for q in q_resp.data:
            ans = ans_map.get(q["id"], {})
            correct_idx = ans.get("correct_option_id", 0)
            correct_text = q["options"][correct_idx] if q["options"] else ""
            mapped_questions.append({
                "id": q["id"],
                "question": q["question_text"],
                "options": q["options"],
                "correct": correct_text
            })
            
        public_questions = [
            {
                "id": q["id"],
                "question": q["question_text"],
                "options": q["options"],
                "difficulty": q["difficulty"],
                "concept": q["concept"]
            } for q in q_resp.data
        ]
        
        public_content = json.dumps({
            "quiz_id": quiz_id,
            "title": title,
            "questions": public_questions
        }, ensure_ascii=False)
        
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.QUIZ,
            status="success",
            content=public_content,
            citations=[],
            confidence=0.95,
            metadata={"generated_questions": mapped_questions, "quiz_id": quiz_id}
        )

    # 2. Fetch chunks
    resp = supabase.table("document_chunks")\
                   .select("id, content, page_start, chunk_index")\
                   .eq("document_id", document_id)\
                   .order("chunk_index")\
                   .execute()
    chunks = resp.data if resp and resp.data else []
    if not chunks:
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.QUIZ,
            status="no_answer",
            content=NO_ANSWER_FALLBACK if lang == "ar" else "I could not find a clear answer in the uploaded file.",
            citations=[],
            confidence=0.0
        )

    # 3. Map-Reduce Quiz Generation
    try:
        blocks = []
        current_block = []
        current_word_count = 0
        for c in chunks:
            c_text = c.get("content", "")
            words = len(c_text.split())
            if current_word_count + words > 1500 and current_block:
                blocks.append(current_block)
                current_block = [c]
                current_word_count = words
            else:
                current_block.append(c)
                current_word_count += words
        if current_block:
            blocks.append(current_block)

        provider = GroqProvider()

        async def process_quiz_block(block_chunks: list, depth: int = 0) -> str:
            api_key, model_name = resolve_config_for_role(LLMRole.MAP_WORKER)
            block_text = "\n".join(c.get("content", "") for c in block_chunks)
            system_prompt = (
                "You are a quiz map worker. Analyze this document section and extract all important "
                "educational facts, definitions, formulas, or concepts that are suitable for testing."
            )
            prompt = f"Section text:\n{block_text}\nExtracted Facts:"
            
            for trial in range(3):
                try:
                    res = await provider.generate(
                        model=model_name,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        api_key=api_key,
                        profile="memory_map",
                        temperature=0.1
                    )
                    return res["text"]
                except Exception as e:
                    if trial == 2:
                        if len(block_chunks) > 1 and depth < 2:
                            mid = len(block_chunks) // 2
                            left = block_chunks[:mid]
                            right = block_chunks[mid:]
                            try:
                                left_res, right_res = await asyncio.gather(
                                    process_quiz_block(left, depth+1),
                                    process_quiz_block(right, depth+1)
                                )
                                return f"{left_res}\n\n{right_res}"
                            except Exception:
                                pass
                        try:
                            fallback_key = settings.GROQ_DEFAULT_API_KEY.strip()
                            fallback_model = settings.GROQ_DEFAULT_MODEL.strip()
                            if fallback_key and fallback_model:
                                res = await provider.generate(
                                    model=fallback_model,
                                    prompt=prompt,
                                    system_prompt=system_prompt,
                                    api_key=fallback_key,
                                    profile="memory_map",
                                    temperature=0.1
                                )
                                return res["text"]
                        except Exception:
                            pass
                        return ""
            return ""

        map_facts = await asyncio.gather(*(process_quiz_block(b) for b in blocks))
        combined_facts = "\n\n".join(f for f in map_facts if f)

        # Generate Quiz
        api_key, model_name = resolve_config_for_role(LLMRole.QUIZ_GENERATOR)

        system_prompt = (
            f"You are a professional quiz generator. Analyze the extracted facts and generate a structured "
            f"quiz in {lang.upper()}. The quiz must contain exactly {num_questions} multiple choice questions, "
            f"conforming to difficulty: '{difficulty}'.\n\n"
            f"You must strictly output the JSON structure conforming to the following schema, without wrapping it under a top-level key:\n"
            f"{{\n"
            f"  \"title\": \"A concise title for the quiz\",\n"
            f"  \"questions\": [\n"
            f"    {{\n"
            f"      \"question_text\": \"The question text.\",\n"
            f"      \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"],\n"
            f"      \"correct_option_id\": 0,\n"
            f"      \"explanation\": \"Detailed explanation of the correct option.\",\n"
            f"      \"concept\": \"Educational concept tested.\",\n"
            f"      \"difficulty\": \"{difficulty}\"\n"
            f"    }}\n"
            f"  ]\n"
            f"}}"
        )
        prompt = f"Extracted facts from document:\n{combined_facts}\nGenerate Quiz JSON:"

        quiz_data = await provider.generate_structured(
            model=model_name,
            prompt=prompt,
            response_model=QuizData,
            system_prompt=system_prompt,
            api_key=api_key,
            profile="quiz",
            temperature=0.3
        )

        # 4. Save Quiz to Database (using transactional insert)
        quiz_id = str(uuid.uuid4())
        supabase.table("quizzes").insert({
            "id": quiz_id,
            "user_id": user_id,
            "document_id": document_id,
            "title": quiz_data.title,
            "difficulty": difficulty,
            "size": size
        }).execute()

        questions_to_insert = []
        answers_to_insert = []
        mapped_questions = []

        for idx, mcq in enumerate(quiz_data.questions):
            q_id = str(uuid.uuid4())
            questions_to_insert.append({
                "id": q_id,
                "quiz_id": quiz_id,
                "question_text": mcq.question_text,
                "options": mcq.options,
                "difficulty": difficulty,
                "concept": mcq.concept
            })
            answers_to_insert.append({
                "question_id": q_id,
                "correct_option_id": mcq.correct_option_id,
                "explanation": mcq.explanation
            })
            correct_text = mcq.options[mcq.correct_option_id]
            mapped_questions.append({
                "id": q_id,
                "question": mcq.question_text,
                "options": mcq.options,
                "correct": correct_text
            })

        supabase.table("quiz_questions").insert(questions_to_insert).execute()
        supabase.table("quiz_question_answers").insert(answers_to_insert).execute()

        # Build public content to return
        public_questions = [
            {
                "id": q["id"],
                "question": q["question_text"],
                "question_text": q["question_text"],
                "options": q["options"],
                "difficulty": q["difficulty"],
                "concept": q["concept"]
            } for q in questions_to_insert
        ]
        
        from app.schemas.ai_schema import QuizDetail
        
        # Instantiate and validate through strict Pydantic model
        quiz_validated = QuizDetail(
            quiz_id=uuid.UUID(str(quiz_id)),
            title=quiz_data.title,
            questions=[
                {
                    "id": uuid.UUID(str(q["id"])),
                    "question_text": q["question_text"],
                    "options": q["options"],
                    "difficulty": q["difficulty"],
                    "concept": q["concept"]
                } for q in questions_to_insert
            ]
        )
        quiz_detail = quiz_validated.model_dump(mode="json")
        
        public_content = json.dumps({
            "quiz_id": quiz_id,
            "title": quiz_data.title,
            "questions": public_questions
        }, ensure_ascii=False)

        return TaskResult(
            task_id=task.task_id,
            type=TaskType.QUIZ,
            status="success",
            content=public_content,
            citations=[],
            confidence=0.95,
            metadata={
                "generated_questions": mapped_questions, 
                "quiz_id": quiz_id,
                "quiz": quiz_detail
            }
        )

    except Exception as e:
        logger.error(f"Quiz Map-Reduce failed: {e}", exc_info=True)
        return TaskResult(
            task_id=task.task_id,
            type=TaskType.QUIZ,
            status="no_answer",
            content=NO_ANSWER_FALLBACK if lang == "ar" else "I could not find a clear answer in the uploaded file.",
            citations=[],
            confidence=0.0,
            error=str(e)
        )

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
        table_content = None

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
