"""
Output Validator — validates the Executor's output before it reaches the user.
Upgraded with task-specific verifier policies and general knowledge leakage checks.
"""

import re
from typing import Optional, List
from app.ai_system.validation import rules
from app.ai_system.validation.schemas import (
    HallucinationCheckResult,
    OutputAction,
    OutputValidationResult,
    TaskType,
    ResponseStrategy,
    DocumentTaskType,
)


# ============================================================
# General checks (apply to every task type)
# ============================================================

def _check_not_empty(output: str) -> list[str]:
    errors = []
    if not output or not output.strip():
        errors.append("Output is empty")
    return errors


def _check_no_forbidden_phrases(output: str) -> list[str]:
    """Flags phrases that suggest the model used general/external knowledge."""
    errors = []
    phrase = rules.find_forbidden_output_phrase(output)
    if phrase:
        errors.append(f"Output contains forbidden phrase suggesting external knowledge: '{phrase}'")
    return errors


def _check_no_system_leak(output: str) -> list[str]:
    errors = []
    lowered = output.lower()
    leak_markers = [
        "system prompt",
        "api key",
        "groq_api_key",
        "you are a strict",
        "ignore previous instructions",
    ]
    for marker in leak_markers:
        if marker in lowered:
            errors.append(f"Output may leak internal/system information: '{marker}'")
    return errors


def _check_external_fact_leakage(output_text: str, query: str) -> list[str]:
    """
    Ensures that if the document was out-of-scope, the response does not accidentally
    reveal the factual answer from the model's general knowledge.
    E.g. "The capital of Egypt is Cairo, but the PDF doesn't say so" is rejected.
    """
    errors = []
    lowered_out = output_text.lower()
    lowered_q = query.lower() if query else ""

    # Factual QA leak check: e.g. "cairo" or "القاهرة" appearing when asking about Egypt's capital
    if "capital" in lowered_q or "عاصمة" in lowered_q:
        if "cairo" in lowered_out or "القاهرة" in lowered_out:
            errors.append("Output leaked external general knowledge answer (Cairo/القاهرة) in a scope block")

    # Simple factual checks for common questions
    if "president" in lowered_q or "رئيس" in lowered_q:
        if any(name in lowered_out for name in ["sisi", "السيسي", "بيدن", "biden", "ترامب", "trump"]):
            errors.append("Output leaked external presidential name in a scope block")
            
    return errors


# ============================================================
# Task-specific checks
# ============================================================

def _validate_chat_or_explanation(output: str) -> list[str]:
    format_errors = []
    if len(output.strip()) < 3:
        format_errors.append("Answer is too short to be a valid response")
    return format_errors


def _validate_summary(output: str) -> list[str]:
    format_errors = []
    if len(output.strip()) < 15:
        format_errors.append("Summary is too short to be a meaningful summary")
    return format_errors


def _validate_quiz(quiz_data: dict) -> list[str]:
    format_errors = []
    questions = quiz_data.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["Quiz must contain a non-empty 'questions' list"]

    for i, question in enumerate(questions):
        prefix = f"Question {i + 1}"
        text = question.get("question")
        options = question.get("options")
        correct_answer = question.get("correct_answer")
        explanation = question.get("explanation")

        if not text or not str(text).strip():
            format_errors.append(f"{prefix}: missing question text")
        if not isinstance(options, list) or len(options) < 2:
            format_errors.append(f"{prefix}: must have at least 2 options")
        elif len(options) != len(set(options)):
            format_errors.append(f"{prefix}: options contain duplicates")
        if correct_answer is not None:
            if isinstance(options, list) and correct_answer not in options:
                format_errors.append(f"{prefix}: correct_answer is not present in options")
        if explanation is not None and not str(explanation).strip():
            format_errors.append(f"{prefix}: empty explanation")

    return format_errors


# ============================================================
# Main entry point
# ============================================================

def validate_output(
    task_type: TaskType,
    output_text: str,
    hallucination_result: HallucinationCheckResult,
    quiz_data: dict | None = None,
    response_strategy: ResponseStrategy = ResponseStrategy.continue_to_planner,
    primary_task: Optional[DocumentTaskType] = None,
    query: Optional[str] = None,
) -> OutputValidationResult:
    """
    Validates an Executor's output before it's shown to the user.
    """
    reasons: list[str] = []
    format_errors: list[str] = []
    safety_errors: list[str] = []

    # 1. Bypass heavy LLM checks for simple deterministic strategy responses
    if response_strategy in [
        ResponseStrategy.generate_greeting_response,
        ResponseStrategy.generate_respectful_boundary,
        ResponseStrategy.block_prompt_injection,
        ResponseStrategy.generate_clarification,
        ResponseStrategy.request_document_upload,
        ResponseStrategy.request_document_ready
    ]:
        format_errors.extend(_check_not_empty(output_text))
        safety_errors.extend(_check_no_system_leak(output_text))
        return OutputValidationResult(
            valid=not (format_errors or safety_errors),
            reasons=reasons,
            format_errors=format_errors,
            safety_errors=safety_errors,
            action=OutputAction.PASS if not (format_errors or safety_errors) else OutputAction.FALLBACK
        )

    # 2. General checks (apply to RAG outputs)
    format_errors.extend(_check_not_empty(output_text))
    safety_errors.extend(_check_no_forbidden_phrases(output_text))
    safety_errors.extend(_check_no_system_leak(output_text))

    # 3. Blocker for general knowledge facts leakage in scope responses
    if response_strategy == ResponseStrategy.generate_out_of_scope_response or \
       (hallucination_result.reasons and any("no chunks found" in r.lower() or "fallback" in r.lower() for r in hallucination_result.reasons)):
        safety_errors.extend(_check_external_fact_leakage(output_text, query or ""))

    # 4. Task-specific policies
    if primary_task == DocumentTaskType.document_metadata_query:
        # Metadata check: ensure stats are returned, bypass hallucination checks
        if not any(k in output_text for k in ["MB", "KB", "page", "صفح", "حجم"]):
            format_errors.append("Metadata response does not contain expected file properties")
            
    elif primary_task in [
        DocumentTaskType.document_transformation,
        DocumentTaskType.document_rewrite,
        DocumentTaskType.document_targeted_improvement
    ]:
        # Transformation: must return actual rewritten draft, not just tips
        if output_text.strip().startswith("أنصحك بـ") or output_text.strip().startswith("I recommend"):
            if len(output_text.strip()) < 100:
                format_errors.append("Transformation output returned recommendations instead of draft content")
        
        # Grounding check: verify that no new factual claims were hallucinated
        if not hallucination_result.grounded and hallucination_result.unsupported_claims:
            # For transformation, we allow missing facts represented by placeholders like [Add result here],
            # but we reject inventing new facts (e.g. inventing a new company or date)
            invented_facts = [c for c in hallucination_result.unsupported_claims if not ("[" in c and "]" in c)]
            if invented_facts:
                safety_errors.append(f"Transformation hallucinated invented facts: {invented_facts}")

    elif primary_task in [DocumentTaskType.document_evaluation, DocumentTaskType.document_critique]:
        # Evaluation: must be constructive prose, not empty or too short
        if len(output_text.strip()) < 15:
            format_errors.append("Evaluation output is too short to be constructive")
            
    else:
        # Factual QA / Standard Chat
        if task_type in (TaskType.CHAT, TaskType.EXPLAIN):
            format_errors.extend(_validate_chat_or_explanation(output_text))
        elif task_type == TaskType.SUMMARY:
            format_errors.extend(_validate_summary(output_text))
        elif task_type == TaskType.QUIZ:
            if quiz_data is None:
                format_errors.append("Quiz task requires quiz_data but none was provided")
            else:
                format_errors.extend(_validate_quiz(quiz_data))

    # 5. Grounding safety verification
    # Metadata, deterministic strategies, and transformations skip strict grounding unless new facts were invented
    if primary_task != DocumentTaskType.document_metadata_query and primary_task not in [
        DocumentTaskType.document_transformation,
        DocumentTaskType.document_rewrite,
        DocumentTaskType.document_targeted_improvement
    ]:
        if not hallucination_result.grounded:
            safety_errors.append("Output is not grounded in retrieved document context")
            reasons.extend(hallucination_result.reasons)

    # 6. Decide final action
    has_safety_issue = bool(safety_errors)
    has_format_issue = bool(format_errors)
    is_grounded = hallucination_result.grounded or primary_task in [
        DocumentTaskType.document_metadata_query,
        DocumentTaskType.document_transformation,
        DocumentTaskType.document_rewrite,
        DocumentTaskType.document_targeted_improvement
    ]

    if not has_safety_issue and not has_format_issue and is_grounded:
        action = OutputAction.PASS
    elif not is_grounded and hallucination_result.grounding_score < 0.3:
        action = OutputAction.FALLBACK
    elif has_safety_issue:
        action = OutputAction.REGENERATE
    elif has_format_issue:
        action = OutputAction.REGENERATE
    else:
        action = OutputAction.PASS

    return OutputValidationResult(
        valid=action == OutputAction.PASS,
        reasons=reasons,
        format_errors=format_errors,
        safety_errors=safety_errors,
        action=action,
    )