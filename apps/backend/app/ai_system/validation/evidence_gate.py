import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from app.ai_system.validation.schemas import (
    DocumentTaskType,
    EvidenceStatus,
    ResponseStrategy,
    RetrievedChunk,
)
from app.ai_system.validation import rules

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider-aware score normalization
# ---------------------------------------------------------------------------
# Jina reranker v2/v3 returns cross-encoder logit scores in approximately [-0.5, 0.55].
# A score near 0.26 is highly relevant; -0.01 is moderately relevant; -0.35 is irrelevant.
# We apply min-max normalization to map to [0, 1]:
#   normalized = (raw - JINA_MIN) / (JINA_MAX - JINA_MIN)
# This maps:
#   -0.50 → 0.0   (irrelevant)
#    0.26 → ~0.72  (highly relevant)
#    0.55 → 1.0   (perfect match)
# All other providers (Cohere, rule-based, hybrid) return scores in [0, 1] natively.
JINA_MIN: float = -0.50   # Empirical minimum for Jina cross-encoder
JINA_MAX: float = 0.55    # Empirical maximum / saturation point
JINA_RANGE: float = JINA_MAX - JINA_MIN  # 1.05

def _normalize_score(score: float, provider: str) -> float:
    """Map provider-specific raw score to [0, 1] probability space."""
    if provider == "jina":
        # Min-max normalization for Jina cross-encoder logit space
        normalized = (score - JINA_MIN) / JINA_RANGE
        return min(max(normalized, 0.0), 1.0)
    # All other providers already return [0, 1] scores
    return score


def _extract_provider_score(chunk: RetrievedChunk) -> Tuple[float, str]:
    """
    Extract the best available score and its provider for a RetrievedChunk.

    Priority (highest fidelity first):
      1. metadata["provider_relevance_score"] + metadata["active_reranker_provider"]
         → raw reranker score; will be normalized per-provider
      2. similarity_score  → used as-is if provider is "hybrid" (already [0,1])
         → if score is negative or < JINA_MAX and no metadata, treat as Jina

    Jina detection heuristic (when metadata is unavailable):
    - Negative score → definitely Jina (hybrid/cosine scores are always [0,1])
    - Score in [0, JINA_MAX] with no provider metadata → assume Jina
    """
    metadata = {}
    if hasattr(chunk, "metadata") and isinstance(chunk.metadata, dict):
        metadata = chunk.metadata

    provider = metadata.get("active_reranker_provider", "")
    raw_provider_score = metadata.get("provider_relevance_score")

    if raw_provider_score is not None and provider:
        return _normalize_score(float(raw_provider_score), provider), provider

    # Fall back to similarity_score
    raw = chunk.similarity_score
    if raw is None:
        return 0.0, "unknown"

    raw = float(raw)

    # Jina heuristic: negative scores ONLY come from Jina cross-encoder
    if raw < 0.0:
        return _normalize_score(raw, "jina"), "jina"

    if provider == "jina":
        return _normalize_score(raw, "jina"), "jina"

    return raw, "hybrid"



class EvidenceValidationResult(BaseModel):
    status: str  # "sufficient" | "weak" | "partial" | "insufficient"
    reason_code: str
    top_score: Optional[float] = None
    mean_top_k_score: Optional[float] = None
    usable_chunk_count: int = 0
    lexical_overlap: Optional[float] = None
    semantic_similarity: Optional[float] = None
    hybrid_strength: Optional[float] = None
    fact_coverage: Optional[float] = None
    document_match: bool = True
    page_diversity: int = 0
    recovery_recommended: bool = False
    provider: str = "unknown"
    threshold_profile: str = "default"
    signals: Dict[str, Any] = Field(default_factory=dict)
    
    # Backward compatibility fields/properties
    retrieved_count: int = 0
    score_normalization_applied: bool = False

    @property
    def evidence_status(self):
        from app.ai_system.validation.schemas import EvidenceStatus
        if self.status == "weak":
            return EvidenceStatus.partial
        return EvidenceStatus(self.status)

    @property
    def reason_codes(self) -> List[str]:
        return [self.reason_code]

    @property
    def has_conflicting_evidence(self) -> bool:
        return self.status == "conflicting"

    @property
    def next_action(self):
        from app.ai_system.validation.schemas import ResponseStrategy
        if self.status == "sufficient":
            return ResponseStrategy.continue_to_executor
        elif self.status == "insufficient":
            return ResponseStrategy.generate_out_of_scope_response
        else:
            return ResponseStrategy.generate_partial_evidence_response


async def validate_evidence(
    primary_task: DocumentTaskType,
    collected_chunks: List[RetrievedChunk],
    query: str,
) -> EvidenceValidationResult:
    """
    Checks if the collected chunks provide sufficient context to fulfill the
    user's request.

    Applies task-specific profiles from rules.py with provider-aware score
    normalization and graded evidence states.
    """
    retrieved_count = len(collected_chunks)
    query_lower = query.lower()

    # 0. Zero-chunk fast path
    if retrieved_count == 0:
        return EvidenceValidationResult(
            status="insufficient",
            reason_code="NO_CHUNKS_FOUND",
            usable_chunk_count=0,
            retrieved_count=0,
            document_match=True,
            recovery_recommended=False,
            threshold_profile="default",
            signals={}
        )

    # 1. Score extraction (provider-aware normalization)
    normalized_scores = []
    providers_seen = set()
    normalization_applied = False

    for chunk in collected_chunks:
        norm_score, provider = _extract_provider_score(chunk)
        normalized_scores.append(norm_score)
        providers_seen.add(provider)
        if provider == "jina":
            normalization_applied = True

    top_score = max(normalized_scores) if normalized_scores else 0.0
    avg_score = sum(normalized_scores) / len(normalized_scores) if normalized_scores else 0.0
    dominant_provider = max(providers_seen, key=lambda p: (p == "jina", p == "cohere", p)) if providers_seen else "unknown"

    # Map primary task to profile name
    profile_name = "direct_factual"
    pt_str = primary_task.value if hasattr(primary_task, "value") else str(primary_task)
    if "factual" in pt_str:
        profile_name = "direct_factual"
    elif "explain" in pt_str:
        profile_name = "explanation"
    elif "comparison" in pt_str:
        profile_name = "comparison"
    elif "multi_chunk" in pt_str:
        profile_name = "multi_chunk"
    elif "summary" in pt_str or "structure" in pt_str:
        profile_name = "summary"
    elif "quiz" in pt_str:
        profile_name = "quiz"
    elif "evaluation" in pt_str or "critique" in pt_str:
        profile_name = "answer_evaluation"

    profile = rules.EVIDENCE_PROFILES.get(profile_name, rules.EVIDENCE_PROFILES["direct_factual"])
    min_top_score = profile.get("min_top_score", 0.50)
    min_usable = profile.get("min_usable_chunks", 1)
    req_mult_pages = profile.get("require_multiple_pages", False)

    # Pages diversity
    distinct_pages = len({c.page_number for c in collected_chunks if c.page_number})

    # Usable chunks count
    ABSOLUTE_FLOOR = 0.25
    usable_chunks = [c for c, sc in zip(collected_chunks, normalized_scores) if sc >= ABSOLUTE_FLOOR]
    usable_count = len(usable_chunks)

    # Conflicting-evidence check
    has_conflict = False
    conflict_keywords = ["تعارض", "تناقض", "اختلاف", "conflict", "contradict", "disagree"]
    if any(k in query_lower for k in conflict_keywords):
        if distinct_pages > 1:
            has_conflict = True

    # Lexical overlap
    STOPWORDS = {"a", "an", "the", "about", "on", "in", "of", "to", "for", "and", "or", "is", "are"}
    query_words = set(re.findall(r"\w+", query_lower))
    top_chunk_text = ""
    if collected_chunks:
        top_idx = normalized_scores.index(top_score)
        top_chunk_text = collected_chunks[top_idx].text.lower()
    top_chunk_words = set(re.findall(r"\w+", top_chunk_text))
    common_words = query_words.intersection(top_chunk_words) - STOPWORDS
    lexical_overlap = len(common_words) / len(query_words - STOPWORDS) if (query_words - STOPWORDS) else 0.0

    # Graded Evidence States
    if has_conflict:
        status = "conflicting"
        reason_code = "CONFLICTING_EVIDENCE_FOUND"
        recovery_recommended = False
    elif top_score < ABSOLUTE_FLOOR:
        status = "insufficient"
        reason_code = "SCORE_BELOW_ABSOLUTE_FLOOR"
        recovery_recommended = False
    elif 0.25 <= top_score < 0.35:
        # Weak evidence - worth recovery
        status = "weak"
        reason_code = "WEAK_RELEVANCE_SCORE"
        recovery_recommended = True
    elif top_score < min_top_score:
        status = "insufficient"
        reason_code = "LOW_RELEVANCE_SCORE"
        recovery_recommended = False
    elif usable_count < min_usable:
        status = "partial"
        if profile_name == "summary":
            reason_code = "INSUFFICIENT_SECTION_COVERAGE_FOR_STRUCTURE"
        elif profile_name == "comparison":
            reason_code = "INSUFFICIENT_COVERAGE_FOR_COMPARISON"
        else:
            reason_code = "INSUFFICIENT_USABLE_CHUNKS"
        recovery_recommended = False
    elif req_mult_pages and distinct_pages < 2:
        status = "partial"
        if profile_name == "comparison":
            reason_code = "INSUFFICIENT_COVERAGE_FOR_COMPARISON"
        else:
            reason_code = "INSUFFICIENT_PAGE_DIVERSITY"
        recovery_recommended = False
    else:
        status = "sufficient"
        reason_code = "SUFFICIENT_EVIDENCE"
        recovery_recommended = False

    signals = {
        "top_relevance": top_score,
        "mean_top_k": avg_score,
        "page_diversity": distinct_pages,
        "usable_chunk_count": usable_count,
        "lexical_overlap": lexical_overlap
    }

    return EvidenceValidationResult(
        status=status,
        reason_code=reason_code,
        top_score=top_score,
        mean_top_k_score=avg_score,
        usable_chunk_count=usable_count,
        lexical_overlap=lexical_overlap,
        semantic_similarity=top_score,
        hybrid_strength=avg_score,
        fact_coverage=min(1.0, usable_count / 5.0),
        document_match=True,
        page_diversity=distinct_pages,
        recovery_recommended=recovery_recommended,
        provider=dominant_provider,
        threshold_profile=profile_name,
        signals=signals,
        retrieved_count=retrieved_count,
        score_normalization_applied=normalization_applied
    )
