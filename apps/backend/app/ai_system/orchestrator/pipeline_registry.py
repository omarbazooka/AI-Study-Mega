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
from app.db.repositories import chat_repository
from app.ai_system.memory import (
    MemoryRetriever, PersonalizationEngine, build_grounded_prompt,
    MemoryStore, ChatMessage, Summarizer
)
from app.ai_system.retrieval import get_document_retriever
from app.ai_system.retrieval.schemas import RetrievalRequest, RetrievalStatus

MOCK_CONFIDENCE = 0.5

memory_retriever = MemoryRetriever()
personalizer = PersonalizationEngine()
store = MemoryStore()
summarizer = Summarizer()
document_retriever = get_document_retriever()

def check_no_answer_trigger(query: str) -> bool:
    """Checks if query simulates requesting information outside the document context."""
    normalized = query.lower()
    return "خارج الملف" in normalized or "outside the file" in normalized

async def execute_common_pipeline_steps(
    task: Task, request: Any, task_type: str, base_content_ar: str, base_content_en: str
) -> TaskResult:
    """
    Executes core pipeline steps:
    1. Check query triggers
    2. Retrieve chunks (RAG)
    3. Check empty chunks -> return fallback
    4. Save user query
    5. Load memory context
    6. Construct grounded prompt
    7. Personalize output
    8. Save assistant response with chunk traceability
    9. Run rolling session summaries
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
            metadata={"mock": True}
        )

    user_id = getattr(request, "user_id", "00000000-0000-0000-0000-000000000000")
    session_id = getattr(request, "session_id", "sess-xyz")
    document_id = getattr(request, "document_id", None)
    lang = getattr(request, "language", "ar")

    # 2. Retrieve relevant chunks via the RAG retrieval module (hybrid search -> rerank ->
    #    token-budgeted context build), scoped to this user + document + query.
    retrieval_result = None
    chunks = []
    if document_id:
        retrieval_result = await document_retriever.retrieve(RetrievalRequest(
            user_id=user_id,
            document_id=document_id,
            query=task.query,
            intent=task_type,
        ))
        # 3. Check for empty/unusable RAG context -> strict grounding fallback
        if retrieval_result.status != RetrievalStatus.FOUND:
            return TaskResult(
                task_id=task.task_id,
                type=task_type,
                status="no_answer",
                content=NO_ANSWER_FALLBACK,
                citations=[],
                confidence=0.0,
                metadata={"mock": True, "retrieval_status": retrieval_result.status.value}
            )
        # Keep the dict-based `chunks` shape used further below for chat/citation logging,
        # sourced from the retriever's already-ranked, budget-fit chunks (not a raw dump).
        chunks = [
            {
                "id": c.chunk_id,
                "content": c.text,
                "page_start": c.page_number or 1,
            }
            for c in retrieval_result.chunks
        ]

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
    
    # Generate the grounded prompt contract
    grounded_prompt = build_grounded_prompt(
        document_context=document_context,
        memory_context=memory_context,
        personalization_instructions=personalization_instructions,
        user_query=task.query
    )
    # logger.debug(f"[Prompt Contract]: {grounded_prompt}")

    # 7. Apply personalization and style adaptations
    base_content = base_content_ar if lang == "ar" else base_content_en
    adapted_content = personalizer.adapt_explanation(
        base_content, memory_context.user_profile, weak_topics=memory_context.weak_topics, topic=task.metadata.get("topic")
    )

    # 8. Save assistant response with chunk traceability
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

    # 9. Rolling summarizer threshold check
    await summarizer.summarize_session(user_id, session_id, force=False)

    # Build response citations directly from the retriever's ranked, deduplicated chunks
    citations = [
        Citation(chunk_id=c.chunk_id, page_number=c.page_number or 1, score=c.score)
        for c in (retrieval_result.chunks if retrieval_result else [])
    ]

    # Collect retrieval info for trace metadata
    retrieval_info = {
        "status": retrieval_result.status.value if retrieval_result else "not_run",
        "confidence": retrieval_result.confidence if retrieval_result else 0.0,
        "chunks_used": len(retrieval_result.chunks) if retrieval_result else 0,
        "latency_ms": retrieval_result.trace.total_retrieval_latency_ms if retrieval_result else 0,
    }

    # Collect memory info for trace metadata
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
            "mock": True,
            "document_id": document_id,
            "retrieved_chunks_count": len(retrieved_chunk_ids),
            "memory_info": memory_info,
            "retrieval_info": retrieval_info
        }
    )


async def run_chat_answer_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Localized QA search pipeline using vector chunks (top-k)."""
    ar_val = f"هذا جواب محاكاة لسؤالك: '{task.query}' استناداً إلى محتوى الملف."
    en_val = f"This is a simulated answer to your question: '{task.query}' grounded strictly in the document."
    return await execute_common_pipeline_steps(task, request, TASK_CHAT_ANSWER, ar_val, en_val)

async def run_explain_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Explanation pipeline for a targeted segment."""
    ar_val = f"شرح مفصل ومبسط للفقرة المطلوبة: '{task.query}'. تم توضيح النقاط الأساسية بلغة واضحة."
    en_val = f"Detailed explanation for: '{task.query}'. The core points have been clarified in simple terms."
    return await execute_common_pipeline_steps(task, request, TASK_EXPLAIN, ar_val, en_val)

async def run_summary_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level summary utilizing all chunks."""
    ar_val = "### ملخص المستند الشامل\n- الفكرة الأولى: هذا ملخص تم إنشاؤه عبر معالجة جميع أجزاء الملف.\n- الفكرة الثانية: تنظيم وهيكلة ممتازة للمفاهيم التعليمية.\n- الفكرة الثالثة: توافق الأهداف التعليمية مع مستويات الطلاب."
    en_val = "### Document Comprehensive Summary\n- Core Idea 1: This summary is generated by processing all chunks of the document.\n- Core Idea 2: Structured organization of educational concepts.\n- Core Idea 3: Alignment of learning objectives with user profiles."
    return await execute_common_pipeline_steps(task, request, TASK_SUMMARY, ar_val, en_val)

async def run_quiz_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Document-level quiz generator utilizing all chunks."""
    diff = getattr(request, "difficulty", "medium") or "medium"
    ar_val = f"### اختبار محاكاة (مستوى: {diff})\n1. ما عاصمة مصر؟\n2. ما الصيغة الكيميائية للماء؟"
    en_val = f"### Simulated Quiz (Level: {diff})\n1. What is the capital of Egypt?\n2. What is the chemical formula of water?"
    
    result = await execute_common_pipeline_steps(task, request, TASK_QUIZ, ar_val, en_val)
    
    # Store quiz questions inside task metadata for sequential consumption
    if result.status == "success":
        lang = getattr(request, "language", "ar")
        result.metadata["generated_questions"] = [
            {"id": "q1", "question": "ما عاصمة مصر؟" if lang == "ar" else "What is the capital of Egypt?", "options": ["القاهرة", "الإسكندرية"] if lang == "ar" else ["Cairo", "Alexandria"], "correct": "القاهرة" if lang == "ar" else "Cairo"},
            {"id": "q2", "question": "ما الصيغة الكيميائية للماء؟" if lang == "ar" else "What is the chemical formula of water?", "options": ["H2O", "CO2"], "correct": "H2O"}
        ]
    return result

async def run_answer_table_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates an answer table based on previous quiz questions."""
    lang = getattr(request, "language", "ar")
    
    # Check if we can dynamically consume quiz questions from previous tasks
    questions = []
    if previous_results:
        for res in previous_results.values():
            # Handle both TaskResult objects and dict results
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
        ar_val = "\n".join(rows)
        en_val = ar_val
    else:
        ar_val = "### جدول الإجابات النموذجية\n| السؤال | الإجابة الصحيحة |\n|---|---|\n| السؤال 1 | القاهرة |\n| السؤال 2 | H2O |"
        en_val = "### Answers Table\n| Question | Correct Answer |\n|---|---|\n| Question 1 | Cairo |\n| Question 2 | H2O |"

    result = await execute_common_pipeline_steps(task, request, TASK_ANSWER_TABLE, ar_val, en_val)
    if result.status == "success":
        result.metadata["consumed_quiz_questions"] = True
    return result

async def run_key_points_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Extracts key points."""
    ar_val = "### النقاط الرئيسية المستخلصة\n- النقطة الأولى والمحورية.\n- النقطة الثانية والتفصيلية.\n- النقطة الثالثة والأثر التعليمي."
    en_val = "### Key Takeaways\n- Primary focal point.\n- Secondary detailed point.\n- Educational outcome point."
    return await execute_common_pipeline_steps(task, request, TASK_KEY_POINTS, ar_val, en_val)

async def run_comparison_table_pipeline(task: Task, request: Any, previous_results: Optional[Dict[str, Any]] = None) -> TaskResult:
    """Generates comparison tables."""
    ar_val = "### جدول مقارنة محاكى\n| الميزة | الموضوع أ | الموضوع ب |\n|---|---|---|\n| التعريف | قيمة أ | قيمة ب |\n| الاستخدام | سياق أ | سياق ب |"
    en_val = "### Simulated Comparison Table\n| Feature | Topic A | Topic B |\n|---|---|---|\n| Definition | Value A | Value B |\n| Use Case | Context A | Context B |"
    return await execute_common_pipeline_steps(task, request, TASK_COMPARISON_TABLE, ar_val, en_val)

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
