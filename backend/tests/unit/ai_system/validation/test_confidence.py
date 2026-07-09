import pytest
from app.ai_system.validation.confidence import calculate_confidence
from app.ai_system.validation.schemas import ConfidenceLabel, ConfidenceAction

def test_confidence_all_high():
    result = calculate_confidence(
        grounding_score=1.0,
        citation_coverage=1.0,
        output_format_score=1.0,
        context_relevance_score=1.0,
        llm_judge_score=1.0,
        has_serious_unsupported_claims=False
    )
    assert result.label == ConfidenceLabel.HIGH
    assert result.action == ConfidenceAction.RETURN

def test_confidence_all_low():
    result = calculate_confidence(
        grounding_score=0.1,
        citation_coverage=0.1,
        output_format_score=0.1,
        context_relevance_score=0.1,
        llm_judge_score=0.1,
        has_serious_unsupported_claims=True
    )
    assert result.label == ConfidenceLabel.LOW
    assert result.action != ConfidenceAction.RETURN
    assert result.action == ConfidenceAction.FALLBACK

def test_confidence_medium_with_unsupported_claims():
    result = calculate_confidence(
        grounding_score=0.7,
        citation_coverage=0.7,
        output_format_score=0.7,
        context_relevance_score=0.7,
        llm_judge_score=0.7,
        has_serious_unsupported_claims=True
    )
    assert result.label == ConfidenceLabel.MEDIUM
    assert result.action == ConfidenceAction.REGENERATE
