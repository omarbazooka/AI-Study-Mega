"""
Verifier — the main orchestrator for the Validation / Safety layer.
Combines input validation, hallucination checking, citation building,
confidence scoring, and output validation into one decision.

This is the single entry point the rest of the system (and later, a
LangGraph node) should call.
"""

from app.ai_system.validation.citation_builder import build_citations
from app.ai_system.validation.confidence import calculate_confidence
from app.ai_system.validation.hallucination_checker import check_hallucination
from app.ai_system.validation.output_validator import validate_output
from app.ai_system.validation.rules import FALLBACK_MESSAGE, MAX_VERIFICATION_RETRIES
from app.ai_system.validation.schemas import (
    RetrievedChunk,
    TaskType,
    VerificationResult,
    VerifierAction,
)


def verify_response(
    user_query: str,
    task_type: TaskType,
    retrieved_chunks: list[RetrievedChunk],
    executor_output: str,
    quiz_data: dict | None = None,
    plan: dict | None = None,
    metadata: dict | None = None,
    retry_count: int = 0,
    embedding_client=None,
    use_llm_judge: bool = True,
) -> VerificationResult:
    """
    Runs the full verification pipeline on an Executor's output and decides
    whether to return it, regenerate it, retrieve more context, or fall back.

    Steps (per validation spec, section 12):
        1. Check grounding against retrieved chunks (hallucination_checker).
        2. Validate output format (output_validator).
        3. Build citations (citation_builder).
        4. Calculate confidence (confidence).
        5. Decide next action.
    """
    metadata = dict(metadata or {})
    metadata["retry_count"] = retry_count

    # --- Safety net: no context at all -> immediate fallback, no LLM calls needed ---
    if not retrieved_chunks:
        return VerificationResult(
            passed=False,
            action=VerifierAction.FALLBACK,
            confidence=0.0,
            reasons=["No retrieved chunks available; cannot ground any answer"],
            unsupported_claims=[],
            citations=[],
            final_answer=FALLBACK_MESSAGE,
            metadata=metadata,
        )

    # --- Max retries safety net ---
    if retry_count > MAX_VERIFICATION_RETRIES:
        return VerificationResult(
            passed=False,
            action=VerifierAction.FALLBACK,
            confidence=0.0,
            reasons=[f"Max retries ({MAX_VERIFICATION_RETRIES}) exceeded"],
            unsupported_claims=[],
            citations=[],
            final_answer=FALLBACK_MESSAGE,
            metadata=metadata,
        )

    # --- Step 1: Hallucination / grounding check ---
    hallucination_result = check_hallucination(
        user_question=user_query,
        draft_answer=executor_output,
        retrieved_chunks=retrieved_chunks,
        embedding_client=embedding_client,
        use_llm_judge=use_llm_judge,
    )

    # --- Step 2: Output format validation ---
    output_result = validate_output(
        task_type=task_type,
        output_text=executor_output,
        hallucination_result=hallucination_result,
        quiz_data=quiz_data,
    )

    # --- Step 3: Build citations ---
    citation_result = build_citations(
        final_answer=executor_output,
        retrieved_chunks=retrieved_chunks,
        claims=hallucination_result.supported_claims + hallucination_result.unsupported_claims,
    )

    # --- Step 4: Confidence scoring ---
    # output_format_score: 1.0 if no format errors, scaled down per error otherwise
    output_format_score = 1.0 if not output_result.format_errors else max(
        0.0, 1.0 - 0.25 * len(output_result.format_errors)
    )
    # context_relevance_score: approximate using average chunk similarity_score if available
    similarity_scores = [c.similarity_score for c in retrieved_chunks if c.similarity_score is not None]
    context_relevance_score = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.5
    # llm_judge_score: reuse grounding_score as a stand-in signal from the judge layer
    llm_judge_score = hallucination_result.grounding_score

    confidence_result = calculate_confidence(
        grounding_score=hallucination_result.grounding_score,
        citation_coverage=citation_result.coverage_score,
        output_format_score=output_format_score,
        context_relevance_score=context_relevance_score,
        llm_judge_score=llm_judge_score,
        has_serious_unsupported_claims=bool(hallucination_result.unsupported_claims),
    )

    # --- Step 5: Decide the final action ---
    reasons: list[str] = []
    reasons.extend(hallucination_result.reasons)
    reasons.extend(output_result.format_errors)
    reasons.extend(output_result.safety_errors)

    action, final_answer, passed = _decide_action(
        output_result_action=output_result.action,
        confidence_action=confidence_result.action,
        hallucination_action=hallucination_result.suggested_action,
        executor_output=executor_output,
    )

    return VerificationResult(
        passed=passed,
        action=action,
        confidence=confidence_result.score,
        reasons=reasons,
        unsupported_claims=hallucination_result.unsupported_claims,
        citations=citation_result.citations,
        final_answer=final_answer,
        metadata=metadata,
    )


def _decide_action(
    output_result_action,
    confidence_action,
    hallucination_action,
    executor_output: str,
) -> tuple[VerifierAction, str | None, bool]:
    """
    Combines the 3 individual decisions (output validator, confidence, hallucination
    checker) into one final action. Fallback always wins (safest option), then
    retrieve_more, then regenerate, then return.

    Priority order (safest first):
        fallback > retrieve_more > regenerate > return/pass
    """
    all_actions = {str(output_result_action.value), str(confidence_action.value), str(hallucination_action.value)}

    if "fallback" in all_actions:
        return VerifierAction.FALLBACK, FALLBACK_MESSAGE, False

    if "retrieve_more" in all_actions:
        return VerifierAction.RETRIEVE_MORE, None, False

    if "regenerate" in all_actions:
        return VerifierAction.REGENERATE, None, False

    # Everything agrees it's safe to return
    return VerifierAction.RETURN, executor_output, True