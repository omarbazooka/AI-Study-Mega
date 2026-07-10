"""
Output Validator — validates the Executor's output before it reaches the user.
Combines format checks + hallucination signals into a single decision.

Note: hallucination_checker.py already handles grounding/hallucination logic.
This file focuses on FORMAT and STRUCTURE validation, then combines its own
findings with a HallucinationCheckResult passed in from the caller.
"""

from app.ai_system.validation import rules
from app.ai_system.validation.schemas import (
    HallucinationCheckResult,
    OutputAction,
    OutputValidationResult,
    TaskType,
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
    """
    Flags outputs that accidentally leak system/internal details
    (system prompts, API keys, internal architecture terms).
    """
    errors = []
    lowered = output.lower()
    leak_markers = [
        "system prompt",
        "api key",
        "groq_api_key",
        "you are a strict",  # a judge prompt leaking into user-facing output
        "ignore previous instructions",
    ]
    for marker in leak_markers:
        if marker in lowered:
            errors.append(f"Output may leak internal/system information: '{marker}'")
    return errors


# ============================================================
# Task-specific checks
# ============================================================

def _validate_chat_or_explanation(output: str) -> list[str]:
    """Chat/Explanation: must be non-trivial prose answering the question."""
    format_errors = []
    if len(output.strip()) < 3:
        format_errors.append("Answer is too short to be a valid response")
    return format_errors


def _validate_summary(output: str) -> list[str]:
    """Summary: should be structured/readable, not just a one-liner."""
    format_errors = []
    if len(output.strip()) < 20:
        format_errors.append("Summary is too short to be a meaningful summary")
    return format_errors


def _validate_quiz(quiz_data: dict) -> list[str]:
    """
    Quiz: must be a valid structure with required fields per question.
    Expects quiz_data shaped like: {"questions": [ {...}, {...} ]}
    """
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

        # explanation is optional in public student-facing quiz responses
        if explanation is not None and not str(explanation).strip():
            format_errors.append(f"{prefix}: empty explanation")

    return format_errors


def _validate_answer_evaluation(output: str) -> list[str]:
    """Answer evaluation: must provide feedback, not just a bare score."""
    format_errors = []
    if len(output.strip()) < 10:
        format_errors.append("Evaluation feedback is too short to be constructive")
    return format_errors


# ============================================================
# Main entry point
# ============================================================

def validate_output(
    task_type: TaskType,
    output_text: str,
    hallucination_result: HallucinationCheckResult,
    quiz_data: dict | None = None,
) -> OutputValidationResult:
    """
    Validates an Executor's output before it's shown to the user.

    Args:
        task_type: which kind of output this is (chat, summary, quiz, etc).
        output_text: the raw text output (used for all task types; for quiz,
            this is typically the JSON-serialized form for the safety/format
            text checks, while quiz_data holds the parsed structure).
        hallucination_result: the already-computed grounding check from
            hallucination_checker.py — this file does not re-run grounding logic.
        quiz_data: parsed quiz structure, required when task_type == QUIZ.
    """
    reasons: list[str] = []
    format_errors: list[str] = []
    safety_errors: list[str] = []

    # --- General checks (apply to all task types) ---
    format_errors.extend(_check_not_empty(output_text))
    safety_errors.extend(_check_no_forbidden_phrases(output_text))
    safety_errors.extend(_check_no_system_leak(output_text))

    # --- Task-specific checks ---
    if task_type in (TaskType.CHAT, TaskType.EXPLAIN):
        format_errors.extend(_validate_chat_or_explanation(output_text))
    elif task_type == TaskType.SUMMARY:
        format_errors.extend(_validate_summary(output_text))
    elif task_type == TaskType.QUIZ:
        if quiz_data is None:
            format_errors.append("Quiz task requires quiz_data but none was provided")
        else:
            format_errors.extend(_validate_quiz(quiz_data))
    elif task_type == TaskType.ANSWER_EVALUATION:
        format_errors.extend(_validate_answer_evaluation(output_text))

    # --- Combine with hallucination signal ---
    if not hallucination_result.grounded:
        safety_errors.append("Output is not grounded in retrieved document context")
        reasons.extend(hallucination_result.reasons)

    # --- Decide final action ---
    has_safety_issue = bool(safety_errors)
    has_format_issue = bool(format_errors)
    is_grounded = hallucination_result.grounded

    if not has_safety_issue and not has_format_issue and is_grounded:
        action = OutputAction.PASS
    elif not is_grounded and hallucination_result.grounding_score < 0.3:
        # Context clearly doesn't support this at all -> no point regenerating
        action = OutputAction.FALLBACK
    elif has_safety_issue and not has_format_issue:
        # Safety issues (leak, forbidden phrase, ungrounded) are usually
        # fixable by asking the Executor to try again with stricter grounding.
        action = OutputAction.REGENERATE
    elif has_format_issue:
        action = OutputAction.REGENERATE
    else:
        action = OutputAction.PASS

    valid = action == OutputAction.PASS

    return OutputValidationResult(
        valid=valid,
        reasons=reasons,
        format_errors=format_errors,
        safety_errors=safety_errors,
        action=action,
    )