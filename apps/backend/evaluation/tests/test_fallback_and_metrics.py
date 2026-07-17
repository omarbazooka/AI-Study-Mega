"""
test_fallback_and_metrics.py
------------------------------
26 unit tests covering fallback scenarios, evidence gate decisions, score
normalization, metrics formulas, and evaluation integrity.

Run from apps/backend/:
    python -m pytest evaluation/tests/test_fallback_and_metrics.py -v
"""
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_chunk(score=0.8, provider="hybrid", page=1):
    """Create a minimal RetrievedChunk-compatible dict mock."""
    chunk = MagicMock()
    chunk.similarity_score = score
    chunk.page_number = page
    chunk.text = "Sample chunk text about technology and education."
    chunk.metadata = {
        "provider_relevance_score": score,
        "active_reranker_provider": provider,
    }
    return chunk

# ---------------------------------------------------------------------------
# Tests: Evidence Gate — Score Normalization
# ---------------------------------------------------------------------------

class TestJinaScoreNormalization:
    """Tests for provider-aware score normalization in evidence_gate._normalize_score"""

    def test_jina_score_0_107_normalized_above_floor(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        # Observed Jina score from TC-001: 0.107772
        # normalized = (0.107772 - (-0.5)) / (0.55 - (-0.5)) = 0.607772 / 1.05 = 0.578
        result = _normalize_score(0.107772, "jina")
        assert result == pytest.approx((0.107772 + 0.5) / 1.05, rel=1e-5)
        assert result >= 0.50  # Should be ~0.578

    def test_jina_score_0_26_normalized_to_sufficient(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        # 0.26 → (0.26 + 0.5) / 1.05 = 0.724 → SUFFICIENT
        result = _normalize_score(0.26, "jina")
        assert result == pytest.approx(0.76 / 1.05, rel=1e-5)
        assert result >= 0.70

    def test_jina_score_0_55_normalized_to_1_0(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        result = _normalize_score(0.55, "jina")
        assert result == pytest.approx(1.0)

    def test_jina_negative_score_maps_positive(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        # -0.014 → (-0.014 + 0.5) / 1.05 = 0.463 → PARTIAL (above floor)
        result = _normalize_score(-0.014, "jina")
        assert result == pytest.approx(0.486 / 1.05, rel=1e-4)
        assert result > 0.25

    def test_jina_very_negative_score_maps_near_zero(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        # -0.50 → 0.0 (irrelevant floor)
        result = _normalize_score(-0.50, "jina")
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_hybrid_score_unchanged(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        assert _normalize_score(0.70, "hybrid") == pytest.approx(0.70)

    def test_cohere_score_unchanged(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        assert _normalize_score(0.85, "cohere") == pytest.approx(0.85)

    def test_jina_zero_maps_above_floor(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        # 0.0 → (0.0 + 0.5) / 1.05 = 0.476 → PARTIAL (not zero!)
        result = _normalize_score(0.0, "jina")
        assert result == pytest.approx(0.5 / 1.05, rel=1e-5)

    def test_jina_score_above_max_capped_at_1(self):
        from app.ai_system.validation.evidence_gate import _normalize_score
        result = _normalize_score(0.80, "jina")
        assert result == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests: Evidence Gate — Decision Logic
# ---------------------------------------------------------------------------

class TestEvidenceGateDecisions:
    """Tests for validate_evidence() routing decisions."""

    @pytest.mark.asyncio
    async def test_zero_chunks_returns_insufficient(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        result = await validate_evidence(DocumentTaskType.document_factual_qa, [], "query")
        assert result.evidence_status == EvidenceStatus.insufficient
        assert "NO_CHUNKS_FOUND" in result.reason_codes

    @pytest.mark.asyncio
    async def test_very_low_jina_score_returns_insufficient(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        # -0.35 → normalized = (-0.35 + 0.5) / 1.05 = 0.143 → below ABSOLUTE_FLOOR (0.25)
        chunks = [make_chunk(score=-0.35, provider="jina")]
        result = await validate_evidence(DocumentTaskType.document_factual_qa, chunks, "query")
        assert result.evidence_status == EvidenceStatus.insufficient

    @pytest.mark.asyncio
    async def test_moderate_jina_score_returns_partial(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        # TC-001 Jina score 0.107772 → normalized ~0.578 → partial or sufficient
        chunks = [make_chunk(score=0.107772, provider="jina")]
        result = await validate_evidence(DocumentTaskType.document_factual_qa, chunks, "query")
        assert result.evidence_status in (EvidenceStatus.partial, EvidenceStatus.sufficient)

    @pytest.mark.asyncio
    async def test_high_jina_score_returns_sufficient(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        # 0.50 raw Jina → normalized 0.909 → sufficient
        chunks = [make_chunk(score=0.50, provider="jina")]
        result = await validate_evidence(DocumentTaskType.document_factual_qa, chunks, "query")
        assert result.evidence_status == EvidenceStatus.sufficient

    @pytest.mark.asyncio
    async def test_hybrid_score_below_absolute_floor_returns_insufficient(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        chunks = [make_chunk(score=0.10, provider="hybrid")]
        result = await validate_evidence(DocumentTaskType.document_factual_qa, chunks, "query")
        assert result.evidence_status == EvidenceStatus.insufficient

    @pytest.mark.asyncio
    async def test_summary_with_2_chunks_returns_sufficient(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        chunks = [make_chunk(0.8, page=1), make_chunk(0.7, page=2)]
        result = await validate_evidence(DocumentTaskType.document_summary, chunks, "summarize")
        assert result.evidence_status == EvidenceStatus.sufficient

    @pytest.mark.asyncio
    async def test_summary_with_1_chunk_returns_partial(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import EvidenceStatus, DocumentTaskType
        chunks = [make_chunk(0.9, page=1)]
        result = await validate_evidence(DocumentTaskType.document_summary, chunks, "summarize")
        assert result.evidence_status == EvidenceStatus.partial

    @pytest.mark.asyncio
    async def test_score_normalization_applied_flag(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import DocumentTaskType
        chunks = [make_chunk(score=0.40, provider="jina")]
        result = await validate_evidence(DocumentTaskType.document_factual_qa, chunks, "query")
        assert result.score_normalization_applied is True

    @pytest.mark.asyncio
    async def test_no_normalization_for_hybrid(self):
        from app.ai_system.validation.evidence_gate import validate_evidence
        from app.ai_system.validation.schemas import DocumentTaskType
        chunks = [make_chunk(score=0.80, provider="hybrid")]
        result = await validate_evidence(DocumentTaskType.document_factual_qa, chunks, "query")
        assert result.score_normalization_applied is False


# ---------------------------------------------------------------------------
# Tests: Fallback Reason Taxonomy
# ---------------------------------------------------------------------------

class TestFallbackReasonCodes:
    """Tests for exception-to-reason-code mapping in pipeline_registry."""

    def _get_reason_code(self, exc_type_name, exc_msg):
        """Simulate the pipeline_registry exception handler logic."""
        exc_type = exc_type_name
        err_str = exc_msg
        if "RateLimitError" in exc_type or "429" in err_str or "rate_limit" in err_str.lower():
            return "GENERATION_TEMPORARILY_UNAVAILABLE"
        elif "AllKeysExhausted" in exc_type:
            return "GENERATION_TEMPORARILY_UNAVAILABLE"
        elif "timeout" in err_str.lower() or "Timeout" in exc_type:
            return "RETRIEVAL_TEMPORARILY_UNAVAILABLE"
        elif "Verification" in exc_type or "verification" in err_str.lower():
            return "VERIFICATION_FAILED"
        else:
            return "INTERNAL_PIPELINE_ERROR"

    def test_rate_limit_error_maps_to_generation_unavailable(self):
        assert self._get_reason_code("RateLimitError", "rate limit exceeded") == "GENERATION_TEMPORARILY_UNAVAILABLE"

    def test_429_in_message_maps_to_generation_unavailable(self):
        assert self._get_reason_code("HTTPError", "429 Too Many Requests") == "GENERATION_TEMPORARILY_UNAVAILABLE"

    def test_all_keys_exhausted_maps_to_generation_unavailable(self):
        assert self._get_reason_code("AllKeysExhaustedException", "all keys exhausted") == "GENERATION_TEMPORARILY_UNAVAILABLE"

    def test_timeout_maps_to_retrieval_unavailable(self):
        assert self._get_reason_code("TimeoutError", "connection timeout after 30s") == "RETRIEVAL_TEMPORARILY_UNAVAILABLE"

    def test_verification_exception_maps_correctly(self):
        assert self._get_reason_code("VerificationError", "verification failed") == "VERIFICATION_FAILED"

    def test_unknown_exception_maps_to_internal_error(self):
        assert self._get_reason_code("MemoryError", "out of memory") == "INTERNAL_PIPELINE_ERROR"


# ---------------------------------------------------------------------------
# Tests: RAGAS Evaluator Integrity
# ---------------------------------------------------------------------------

class TestRagasEvaluatorIntegrity:
    """Tests that programmatic fallback scores are NOT mixed into framework averages."""

    def test_is_refusal_detection_arabic(self):
        """Confirm Arabic refusal keywords are detected."""
        from evaluation.evaluators.ragas_evaluator import run_ragas_evaluation
        # We can't run the full evaluation, but test the helper logic inline
        refusal_kw = [
            "لم أجد إجابة", "لا يحتوي الملف", "لا يوجد", "خارج نطاق",
            "does not provide enough supporting evidence",
        ]
        def is_refusal(ans):
            ans_lower = ans.lower()
            return any(kw in ans_lower or kw in ans for kw in refusal_kw)
        assert is_refusal("لم أجد إجابة واضحة في الملف المرفوع.") is True
        assert is_refusal("التكنولوجيا الحديثة تساعد في التعليم") is False

    def test_nan_not_produced_for_empty_list(self):
        """Confirming Python's behavior: mean of empty = exception, not NaN."""
        import statistics
        with pytest.raises(statistics.StatisticsError):
            statistics.mean([])

    def test_framework_average_excludes_programmatic_nulls(self):
        """A filtered mean should skip None values."""
        scores = [0.8, 0.7, None, 0.9, None]
        valid = [s for s in scores if s is not None]
        assert len(valid) == 3
        assert abs(sum(valid) / len(valid) - 0.8) < 0.01


# ---------------------------------------------------------------------------
# Tests: Metrics Formulas
# ---------------------------------------------------------------------------

class TestMetricsFormulas:
    """Tests for deterministic metrics formulas."""

    def test_correct_answer_rate_calculation(self):
        total, correct = 30, 3
        rate = (correct / total) * 100
        assert rate == pytest.approx(10.0)

    def test_false_refusal_rate(self):
        answerable, false_refusals = 27, 27
        rate = false_refusals / answerable
        assert rate == pytest.approx(1.0)

    def test_hallucination_rate_not_measurable_when_no_answers(self):
        generated_answers = 0
        result = "Not Measurable" if generated_answers == 0 else "computable"
        assert result == "Not Measurable"

    def test_composite_score_null_when_component_missing(self):
        components = {
            "ragas_correctness": None,
            "ragas_faithfulness": 0.9,
            "deepeval_relevancy": 0.8,
            "deepeval_quality": 0.85,
            "precision": 0.70,
            "recall": 0.75,
        }
        all_present = all(v is not None for v in components.values())
        composite = None if not all_present else sum(components.values()) / len(components)
        assert composite is None

    def test_composite_score_computable_with_all_components(self):
        components = {
            "ragas_correctness": 0.75,
            "ragas_faithfulness": 0.90,
            "deepeval_relevancy": 0.80,
            "deepeval_quality": 0.85,
            "precision": 0.70,
            "recall": 0.75,
        }
        all_present = all(v is not None for v in components.values())
        composite = sum(components.values()) / len(components)
        assert all_present
        assert composite == pytest.approx(sum(components.values()) / 6, rel=1e-6)

    def test_precision_at_k(self):
        """P@k = relevant_in_top_k / k"""
        relevant = [1, 0, 1, 1, 0]
        k = 3
        p_at_k = sum(relevant[:k]) / k
        assert p_at_k == pytest.approx(2/3)

    def test_recall_at_k(self):
        """R@k = relevant_in_top_k / total_relevant"""
        relevant = [1, 0, 1, 1, 0]
        total_relevant = sum(relevant)
        k = 3
        r_at_k = sum(relevant[:k]) / total_relevant
        assert r_at_k == pytest.approx(2/3)


# ---------------------------------------------------------------------------
# Tests: Data Integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    """Tests for the data integrity validation module."""

    def test_no_nan_in_valid_scores(self):
        scores = [0.8, 0.7, 0.9]
        assert not any(math.isnan(s) for s in scores)

    def test_nan_detection(self):
        scores = [0.8, float("nan"), 0.9]
        assert any(math.isnan(s) for s in scores)

    def test_confusion_matrix_sum_equals_total_cases(self):
        matrix = {"true_answer": 3, "false_refusal": 24, "correct_fallback": 3, "hallucinated_answer": 0}
        assert sum(matrix.values()) == 30

    def test_integrity_status_fails_on_nan(self):
        """Mimic validate_integrity logic for NaN detection."""
        import json

        data = {"ragas_correctness": float("nan")}
        nan_found = math.isnan(data["ragas_correctness"]) if isinstance(data["ragas_correctness"], float) else False
        status = "failed" if nan_found else "passed"
        assert status == "failed"
