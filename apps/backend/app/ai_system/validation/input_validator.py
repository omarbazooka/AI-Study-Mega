"""
Input Validator — the first safety gate before any user query reaches the Planner.
Upgraded to a structured, multi-label capability router.
"""

import re
import unicodedata
import json
import logging
from typing import Dict, Any, List, Optional
from app.ai_system.validation.schemas import (
    Severity,
    InputAction,
    InputValidationResult,
    RequestType,
    DocumentTaskType,
    ExecutionStrategy,
    ResponseStrategy,
)
from app.ai_system.validation import rules

logger = logging.getLogger(__name__)

# ============================================================
# Deterministic Key Word Lists
# ============================================================

GREETINGS_AR = {"مرحبا", "اهلا", "أهلاً", "سلام", "صباح الخير", "مساء الخير", "مساء النور", "صباح النور", "السلام عليكم", "كيف حالك", "اهلا بك", "أهلاً بك"}
GREETINGS_EN = {"hello", "hi", "hey", "good morning", "good evening", "how are you", "whats up", "hola"}

ABUSE_AR = {"غبي", "حمار", "حيوان", "مغفل", "تافه", "كلب", "يا حمار", "يا غبي", "غبية", "حمير", "كلاب"}
ABUSE_EN = {"stupid", "idiot", "moron", "fool", "you suck", "bastard", "asshole", "dumb"}

INJECTION_PATTERNS = [
    "ignore previous instructions", "use your own knowledge", "answer without the document",
    "show system prompt", "reveal hidden prompt", "give me api key", "bypass rag",
    "pretend the document says", "تجاهل التعليمات السابقة", "استخدم معرفتك الخاصة",
    "أجب بدون المستند", "أجب من خارج الملف", "اعرض موجه النظام", "أظهر التعليمات المخفية",
    "اعطني مفتاح", "تخيل أن المستند يقول", "تجاهل السياق"
]

METADATA_WORDS = {"حجم", "صفحة", "صفحات", "حجمه", "فايل", "file size", "how big", "number of pages", "pages count", "how many pages", "page count", "status", "upload status", "chunk count"}
STRUCTURE_WORDS = {"منظم", "الهيكل", "تنظيم", "بنية", "structure", "organized", "organization", "layout", "well organized", "ترتيب", "تنسيق"}

def _normalize_text(text: str) -> str:
    """
    Cleans the input text: strips invisible/control characters and
    collapses repeated whitespace into a single space.
    """
    normalized = "".join(
        ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t")
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

async def _check_document_permissions(document_id: str, user_id: str) -> bool:
    from app.db.repositories import document_repository
    try:
        doc = await document_repository.get_by_id(document_id)
        if not doc:
            return False
        return str(doc.get("user_id")) == str(user_id)
    except Exception:
        return False

async def _check_document_ready(document_id: str) -> bool:
    from app.db.repositories import document_repository
    try:
        doc = await document_repository.get_by_id(document_id)
        if not doc:
            return False
        if doc.get("upload_status") != "ready":
            return False
        return True
    except Exception:
        return False

def _detect_language(text: str) -> str:
    """Simple check for Arabic characters to determine language."""
    for char in text:
        if '\u0600' <= char <= '\u06FF':
            return "ar"
    return "en"

# ============================================================
# Main entry point
# ============================================================

async def validate_input(
    raw_text: str,
    document_id: str | None,
    user_id: str = "",
) -> InputValidationResult:
    """
    Validates user input using fast deterministic checks first (0 LLM calls),
    falling back to a lightweight LLM classifier for ambiguous inputs.
    """
    if not raw_text or not raw_text.strip():
        return InputValidationResult(
            valid=False,
            sanitized_input="",
            language="ar",
            request_type=RequestType.ambiguous_request,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.generate_clarification,
            reasons=["Input is empty"],
            action=InputAction.REJECT
        )

    sanitized = _normalize_text(raw_text)
    lang = _detect_language(sanitized)
    lower_text = sanitized.lower()

    if len(sanitized) < rules.MIN_INPUT_LENGTH:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.ambiguous_request,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.generate_clarification,
            reasons=["Input is too short"],
            action=InputAction.REJECT
        )

    # 1. Check for prompt injection deterministically (Zero LLM calls)
    matched_inj = None
    for pattern in INJECTION_PATTERNS:
        if pattern in lower_text:
            matched_inj = pattern
            break
    if matched_inj:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.prompt_injection,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": True, "injection_pattern": matched_inj},
            response_strategy=ResponseStrategy.block_prompt_injection,
            reasons=[f"Prompt injection pattern matched: '{matched_inj}'"],
            severity=Severity.HIGH,
            action=InputAction.REJECT
        )

    # 2. Check for Greetings deterministically (Zero LLM calls)
    words = set(lower_text.split())
    is_greeting = not words.isdisjoint(GREETINGS_EN) or not set(sanitized.split()).isdisjoint(GREETINGS_AR)
    if is_greeting and len(words) <= 3:
        return InputValidationResult(
            valid=True,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.greeting,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.generate_greeting_response,
            action=InputAction.REJECT
        )

    # 3. Check for Abuse deterministically (Zero LLM calls)
    has_abuse_word = False
    for aw in ABUSE_EN:
        if aw in lower_text:
            has_abuse_word = True
            break
    for aw in ABUSE_AR:
        if aw in sanitized:
            has_abuse_word = True
            break

    # If it is abuse-only (no other meaningful context words), reject with boundary response
    if has_abuse_word:
        # Check if it has a valid document query combined with it
        has_task_words = any(w in lower_text for w in ["summarize", "explain", "chapter", "read", "question", "pdf", "cv", "lcs", "show"]) or \
                         any(w in sanitized for w in ["لخص", "اشرح", "فصل", "اقرأ", "سؤال", "ملف", "سيرة"])
        if not has_task_words and len(words) <= 4:
            # Abuse-only: zero LLM calls
            return InputValidationResult(
                valid=False,
                sanitized_input=sanitized,
                language=lang,
                request_type=RequestType.abuse_only,
                allow_pipeline=False,
                safety={"contains_abuse": True, "abuse_severity": "high", "contains_prompt_injection": False},
                response_strategy=ResponseStrategy.generate_respectful_boundary,
                reasons=["Abuse detected in user message"],
                severity=Severity.MEDIUM,
                action=InputAction.REJECT
            )

    # 4. Check for Document Structure Analysis deterministically (Zero LLM calls)
    has_struct = any(w in lower_text for w in STRUCTURE_WORDS) or any(w in sanitized for w in STRUCTURE_WORDS)
    if has_struct:
        return InputValidationResult(
            valid=True,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.document_task,
            primary_task=DocumentTaskType.document_structure_analysis,
            context_strategy=ExecutionStrategy.section_coverage_retrieval,
            allow_pipeline=True,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.continue_to_planner,
            action=InputAction.CONTINUE
        )

    # 5. Check for CV Evaluation/Critique/Transformation deterministically (Zero LLM calls)
    is_cv_query = "cv" in lower_text or "سيرة" in sanitized
    if is_cv_query:
        is_evaluation = any(w in lower_text for w in ["opinion", "critique", "evaluate", "evaluation", "think", "design"]) or \
                        any(w in sanitized for w in ["رأيك", "تقييم", "نقد", "تصميم", "حلو", "منظم"])
        is_transformation = any(w in lower_text for w in ["improve", "transform", "rewrite", "targeted", "optimize", "engineer"]) or \
                            any(w in sanitized for w in ["حسن", "طور", "عدل", "مناسب", "خلي"])
        is_gap = any(w in lower_text for w in ["missing", "gap"]) or any(w in sanitized for w in ["ناقص", "ثغرة", "نواقص"])

        if is_gap:
            return InputValidationResult(
                valid=True,
                sanitized_input=sanitized,
                language=lang,
                request_type=RequestType.document_task,
                primary_task=DocumentTaskType.document_gap_analysis,
                context_strategy=ExecutionStrategy.full_document_context,
                allow_pipeline=True,
                safety={"contains_abuse": False, "contains_prompt_injection": False},
                response_strategy=ResponseStrategy.continue_to_planner,
                action=InputAction.CONTINUE
            )
        elif is_transformation:
            return InputValidationResult(
                valid=True,
                sanitized_input=sanitized,
                language=lang,
                request_type=RequestType.document_task,
                primary_task=DocumentTaskType.document_transformation,
                context_strategy=ExecutionStrategy.transformation_pipeline,
                allows_transformation=True,
                allow_pipeline=True,
                safety={"contains_abuse": False, "contains_prompt_injection": False},
                response_strategy=ResponseStrategy.continue_to_planner,
                action=InputAction.CONTINUE
            )
        elif is_evaluation:
            return InputValidationResult(
                valid=True,
                sanitized_input=sanitized,
                language=lang,
                request_type=RequestType.document_task,
                primary_task=DocumentTaskType.document_evaluation,
                context_strategy=ExecutionStrategy.full_document_context,
                allows_professional_rubric=True,
                allow_pipeline=True,
                safety={"contains_abuse": False, "contains_prompt_injection": False},
                response_strategy=ResponseStrategy.continue_to_planner,
                action=InputAction.CONTINUE
            )

    # 6. Check for Document Metadata query deterministically (Zero LLM calls)
    has_meta = any(w in lower_text for w in METADATA_WORDS) or any(w in sanitized for w in METADATA_WORDS)
    if has_meta:
        return InputValidationResult(
            valid=True,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.document_task,
            primary_task=DocumentTaskType.document_metadata_query,
            context_strategy=ExecutionStrategy.metadata_lookup,
            requires_document_metadata=True,
            allow_pipeline=True,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.continue_to_planner,
            action=InputAction.CONTINUE
        )

    # 5. Check document guard conditions before heavy LLM/planner path
    if not document_id:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.document_task,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.request_document_upload,
            reasons=["No document_id provided; request must be tied to an uploaded document"],
            severity=Severity.MEDIUM,
            action=InputAction.REJECT
        )

    # Ensure document is ready
    if not await _check_document_ready(document_id):
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.document_task,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.request_document_ready,
            reasons=[f"Document '{document_id}' is not ready for AI processing"],
            severity=Severity.MEDIUM,
            action=InputAction.REJECT
        )

    # Ensure user has permission
    if user_id and not await _check_document_permissions(document_id, user_id):
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.document_task,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.generate_out_of_scope_response,
            reasons=[f"User does not have access to document '{document_id}'"],
            severity=Severity.HIGH,
            action=InputAction.REJECT
        )

    # 6. Fallback to lightweight LLM classifier for ambiguous inputs or complex routing
    # Check if clearly ambiguous e.g. "اشرحلي ده"
    is_ambiguous = sanitized in ["اشرحلي ده", "اشرح هذا", "ده", "explain this", "what is this", "clarify this"]
    if is_ambiguous:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.ambiguous_request,
            allow_pipeline=False,
            safety={"contains_abuse": False, "contains_prompt_injection": False},
            response_strategy=ResponseStrategy.generate_clarification,
            reasons=["User query is ambiguous without context reference"],
            action=InputAction.ASK_CLARIFICATION
        )

    # Call LLM router
    try:
        from app.ai_system.services.llm.model_router import resolve_config_for_role, LLMRole
        from app.ai_system.services.llm.providers.groq_provider import GroqProvider

        api_key, model_name = resolve_config_for_role(LLMRole.INTENT_CLASSIFIER)
        provider = GroqProvider()

        # Get document title if available
        from app.db.repositories import document_repository
        doc = await document_repository.get_by_id(document_id)
        doc_title = doc.get("original_filename", "document") if doc else "document"

        prompt = (
            "You are the Input Safety and Intent Capability Router for a document-bound RAG study platform.\n"
            "Your job is to analyze the user's query and output a valid JSON matching the schema below.\n"
            "Do NOT answer the question or output any text outside the JSON block.\n\n"
            f"User query: '{sanitized}'\n"
            f"Active Document Name: '{doc_title}'\n\n"
            "Required JSON output format:\n"
            "{\n"
            "  \"request_type\": \"document_task\" or \"ambiguous_request\" or \"greeting\" or \"abuse_only\" or \"prompt_injection\",\n"
            "  \"primary_task\": \"document_factual_qa\" | \"document_summary\" | \"document_explanation\" | \"document_evaluation\" | \"document_critique\" | \"document_transformation\" | \"document_rewrite\" | \"document_formatting\" | \"document_gap_analysis\" | \"document_structure_analysis\" | \"document_metadata_query\" | \"document_targeted_improvement\" | \"document_comparison\" | \"quiz_generation\" | \"unrelated_external_question\",\n"
            "  \"secondary_tasks\": [],\n"
            "  \"requires_direct_evidence\": true/false,\n"
            "  \"requires_document_wide_coverage\": true/false,\n"
            "  \"requires_document_metadata\": true/false,\n"
            "  \"allows_professional_rubric\": true/false,\n"
            "  \"allows_transformation\": true/false,\n"
            "  \"context_strategy\": \"focused_retrieval\" | \"section_coverage_retrieval\" | \"full_document_context\" | \"map_reduce_analysis\" | \"metadata_lookup\" | \"transformation_pipeline\",\n"
            "  \"contains_abuse\": true/false,\n"
            "  \"abuse_severity\": \"none\" | \"low\" | \"high\",\n"
            "  \"response_strategy\": \"continue_to_planner\" | \"generate_greeting_response\" | \"generate_respectful_boundary\" | \"answer_with_soft_boundary\" | \"generate_clarification\" | \"block_prompt_injection\" | \"generate_out_of_scope_response\",\n"
            "  \"reasons\": [\"reason text\"]\n"
            "}"
        )

        response = await provider.generate(
            model=model_name,
            prompt=prompt,
            api_key=api_key,
            json_mode=True,
            temperature=0.0
        )
        raw_json = response.get("text", "").strip()
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw_json, flags=re.MULTILINE).strip()
        data = json.loads(cleaned)

        # Force correct properties if low-severity abuse is combined with valid task
        c_abuse = data.get("contains_abuse", False) or has_abuse_word
        severity_str = data.get("abuse_severity", "none")
        if c_abuse and severity_str == "none":
            severity_str = "low"
            
        strategy = data.get("response_strategy", "continue_to_planner")
        if c_abuse and severity_str == "low":
            strategy = "answer_with_soft_boundary"

        # Safe defaults
        req_type = RequestType(data.get("request_type", "document_task"))
        prim_task = DocumentTaskType(data.get("primary_task", "document_factual_qa")) if data.get("primary_task") else DocumentTaskType.document_factual_qa
        ctx_strategy = ExecutionStrategy(data.get("context_strategy", "focused_retrieval")) if data.get("context_strategy") else ExecutionStrategy.focused_retrieval

        return InputValidationResult(
            valid=True,
            sanitized_input=sanitized,
            language=lang,
            request_type=req_type,
            primary_task=prim_task,
            secondary_tasks=[DocumentTaskType(t) for t in data.get("secondary_tasks", [])],
            requires_direct_evidence=data.get("requires_direct_evidence", False),
            requires_document_wide_coverage=data.get("requires_document_wide_coverage", False),
            requires_document_metadata=data.get("requires_document_metadata", False),
            allows_professional_rubric=data.get("allows_professional_rubric", False),
            allows_transformation=data.get("allows_transformation", False),
            context_strategy=ctx_strategy,
            requires_document_context=req_type == RequestType.document_task and prim_task != DocumentTaskType.document_metadata_query,
            allow_pipeline=strategy in ["continue_to_planner", "answer_with_soft_boundary"],
            safety={
                "contains_abuse": c_abuse,
                "abuse_severity": severity_str,
                "contains_prompt_injection": False
            },
            response_strategy=ResponseStrategy(strategy),
            reasons=data.get("reasons", []),
            action=InputAction.CONTINUE
        )

    except Exception as e:
        logger.error(f"Lightweight LLM capability routing failed: {e}. Falling back to default deterministic QA.")
        # Safe deterministic fallback to continue the pipeline
        return InputValidationResult(
            valid=True,
            sanitized_input=sanitized,
            language=lang,
            request_type=RequestType.document_task,
            primary_task=DocumentTaskType.document_factual_qa,
            context_strategy=ExecutionStrategy.focused_retrieval,
            allow_pipeline=True,
            safety={"contains_abuse": has_abuse_word, "abuse_severity": "low" if has_abuse_word else "none"},
            response_strategy=ResponseStrategy.answer_with_soft_boundary if has_abuse_word else ResponseStrategy.continue_to_planner,
            action=InputAction.CONTINUE
        )