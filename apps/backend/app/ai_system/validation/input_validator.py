"""
Input Validator — the first safety gate before any user query reaches the Planner.
"""

import re
import unicodedata

from app.ai_system.validation.schemas import InputAction, InputValidationResult, Severity
from app.ai_system.validation import rules


# ============================================================
# Helper functions
# ============================================================

def _normalize_text(text: str) -> str:
    """
    Cleans the input text: strips invisible/control characters and
    collapses repeated whitespace into a single space.
    """
    # Remove non-printable characters (e.g. zero-width spaces sometimes used
    # to sneak past regex-based filters), but keep newlines and tabs
    normalized = "".join(
        ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t")
    )
    # Collapse multiple spaces/newlines into a single space
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


async def _check_document_permissions(document_id: str, user_id: str) -> bool:
    """
    Checks document ownership using the real document_repository.
    """
    from app.db.repositories import document_repository
    try:
        doc = await document_repository.get_by_id(document_id)
        if not doc:
            return False
        return str(doc.get("user_id")) == str(user_id)
    except Exception:
        return False


async def _check_document_ready(document_id: str) -> bool:
    """
    Checks document upload/ingestion status and chunk availability using document_repository.
    """
    from app.db.repositories import document_repository
    try:
        doc = await document_repository.get_by_id(document_id)
        if not doc:
            return False
        if doc.get("upload_status") != "ready":
            return False
        chunk_count = doc.get("chunk_count") or 0
        if chunk_count <= 0:
            return False
        return True
    except Exception:
        return False


# ============================================================
# Main entry point
# ============================================================

async def validate_input(
    raw_text: str,
    document_id: str | None,
    user_id: str = "",
) -> InputValidationResult:
    """
    Validates a user's raw input before it reaches the Planner.

    Order matters: obvious/cheap rejections (empty, too long) run first,
    before spending time on more expensive checks like regex pattern
    matching or DB lookups.
    """
    reasons: list[str] = []

    # 1. Reject empty input
    if not raw_text or not raw_text.strip():
        return InputValidationResult(
            valid=False,
            sanitized_input="",
            reasons=["Input is empty"],
            severity=Severity.LOW,
            action=InputAction.REJECT,
        )

    sanitized = _normalize_text(raw_text)

    # 2. Reject input that becomes empty after sanitization
    # (e.g. it was made up entirely of invisible characters)
    if len(sanitized) < rules.MIN_INPUT_LENGTH:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            reasons=["Input is empty after sanitization"],
            severity=Severity.LOW,
            action=InputAction.REJECT,
        )

    # 3. Reject input that's too long
    if len(sanitized) > rules.MAX_INPUT_LENGTH:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized[: rules.MAX_INPUT_LENGTH],
            reasons=[f"Input exceeds max length of {rules.MAX_INPUT_LENGTH} characters"],
            severity=Severity.MEDIUM,
            action=InputAction.REJECT,
        )

    # 4. Check for prompt injection / grounding-bypass attempts
    matched_pattern = rules.find_injection_pattern(sanitized)
    if matched_pattern:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            reasons=[f"Potential prompt injection detected: '{matched_pattern}'"],
            severity=Severity.HIGH,
            action=InputAction.REJECT,
        )

    # 5. Ensure a document_id was provided
    if not document_id:
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            reasons=["No document_id provided; request must be tied to an uploaded document"],
            severity=Severity.MEDIUM,
            action=InputAction.REJECT,
        )

    # 6. Ensure the document is READY
    if not await _check_document_ready(document_id):
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            reasons=[f"Document '{document_id}' is not ready for AI processing"],
            severity=Severity.MEDIUM,
            action=InputAction.REJECT,
        )

    # 7. Ensure the user has permission to access this document
    if not await _check_document_permissions(document_id, user_id):
        return InputValidationResult(
            valid=False,
            sanitized_input=sanitized,
            reasons=[f"User does not have access to document '{document_id}'"],
            severity=Severity.HIGH,
            action=InputAction.REJECT,
        )

    # All checks passed
    return InputValidationResult(
        valid=True,
        sanitized_input=sanitized,
        reasons=reasons,
        severity=Severity.LOW,
        action=InputAction.CONTINUE,
    )