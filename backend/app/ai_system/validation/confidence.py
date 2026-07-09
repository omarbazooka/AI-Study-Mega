"""
Confidence Scoring — combines several sub-scores into one final confidence
score + label + recommended action for a given AI response.
"""

from app.ai_system.validation.rules import (
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    CONFIDENCE_WEIGHTS,
)
from app.ai_system.validation.schemas import ConfidenceAction, ConfidenceLabel, ConfidenceResult


def _label_for_score(score: float) -> ConfidenceLabel:
    """Maps a numeric score to a human-readable confidence label."""
    if score >= CONFIDENCE_HIGH_THRESHOLD:
        return ConfidenceLabel.HIGH
    if score >= CONFIDENCE_MEDIUM_THRESHOLD:
        return ConfidenceLabel.MEDIUM
    return ConfidenceLabel.LOW


def _action_for_label(label: ConfidenceLabel, grounding_score: float, has_serious_unsupported_claims: bool) -> ConfidenceAction:
    """
    Decision rules (per validation spec, section 11):
    - confidence < 0.60 -> never return directly.
    - medium confidence -> only allow if grounding is acceptable and there are
      no serious unsupported claims.
    - high confidence -> return the answer with citations.
    """
    if label == ConfidenceLabel.HIGH:
        return ConfidenceAction.RETURN

    if label == ConfidenceLabel.MEDIUM:
        if grounding_score >= CONFIDENCE_MEDIUM_THRESHOLD and not has_serious_unsupported_claims:
            return ConfidenceAction.RETURN
        return ConfidenceAction.REGENERATE

    # LOW confidence
    if grounding_score < 0.3:
        # Grounding is very poor -> more retrieval likely won't help either,
        # the context probably just doesn't cover this question.
        return ConfidenceAction.FALLBACK
    return ConfidenceAction.RETRIEVE_MORE


def calculate_confidence(
    grounding_score: float,
    citation_coverage: float,
    output_format_score: float,
    context_relevance_score: float,
    llm_judge_score: float,
    has_serious_unsupported_claims: bool = False,
) -> ConfidenceResult:
    """
    Calculates the final confidence score using the weighted formula:
        40% grounding_score
        20% citation_coverage
        15% output_format_score
        15% context_relevance_score
        10% llm_judge_score

    All input scores are expected to already be normalized to the 0.0-1.0 range.
    """
    factors = {
        "grounding_score": grounding_score,
        "citation_coverage": citation_coverage,
        "output_format_score": output_format_score,
        "context_relevance_score": context_relevance_score,
        "llm_judge_score": llm_judge_score,
    }

    score = sum(factors[key] * weight for key, weight in CONFIDENCE_WEIGHTS.items())
    # Clamp to [0.0, 1.0] in case of any floating point drift
    score = max(0.0, min(1.0, score))

    label = _label_for_score(score)
    action = _action_for_label(label, grounding_score, has_serious_unsupported_claims)

    return ConfidenceResult(
        score=score,
        label=label,
        factors=factors,
        action=action,
    )