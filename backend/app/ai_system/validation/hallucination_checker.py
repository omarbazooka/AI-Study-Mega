"""
Hallucination Checker — detects claims in an AI answer that are NOT
supported by the retrieved document chunks.

Runs 3 layers together (never relies on just one):
  Layer 1: rule-based checks (fast, free, catches obvious cases)
  Layer 2: similarity-based checks (needs an embedding client)
  Layer 3: LLM-as-a-Judge (uses Groq, most expensive, most accurate)
"""

import json
import re

from groq import Groq

from app.ai_system.validation import rules
from app.ai_system.validation.exceptions import LLMJudgeError
from app.ai_system.validation.prompts import build_grounding_judge_prompt
from app.ai_system.validation.schemas import (
    HallucinationAction,
    HallucinationCheckResult,
    RetrievedChunk,
)


# ============================================================
# Layer 1: Rule-based checks
# ============================================================

_NUMBER_PATTERN = re.compile(r"\b\d[\d,.:]*\b")
_DATE_PATTERN = re.compile(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b|\b(19|20)\d{2}\b")


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_PATTERN.findall(text))


def _rule_based_check(answer: str, context_text: str) -> tuple[list[str], list[str]]:
    """
    Returns (reasons, forbidden_phrases_found).

    - Flags numbers in the answer that don't appear anywhere in the context.
    - Flags forbidden phrases (e.g. "generally speaking") that signal the
      model is leaning on outside/general knowledge.
    """
    reasons: list[str] = []

    answer_numbers = _extract_numbers(answer)
    context_numbers = _extract_numbers(context_text)
    unsupported_numbers = answer_numbers - context_numbers
    if unsupported_numbers:
        reasons.append(f"Numbers not found in context: {sorted(unsupported_numbers)}")

    forbidden_phrase = rules.find_forbidden_output_phrase(answer)
    if forbidden_phrase:
        reasons.append(f"Forbidden phrase suggesting external knowledge: '{forbidden_phrase}'")

    return reasons, ([forbidden_phrase] if forbidden_phrase else [])


# ============================================================
# Layer 2: Similarity-based checks
# ============================================================

def _split_into_claims(answer: str) -> list[str]:
    """Splits the answer into sentence-level claims for per-sentence checking."""
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [s.strip() for s in sentences if s.strip()]


def _similarity_check(
    claims: list[str],
    retrieved_chunks: list[RetrievedChunk],
    embedding_client=None,
) -> tuple[list[str], list[str], float]:
    """
    Compares each claim against the retrieved chunks using embeddings.

    If no embedding_client is provided, falls back to a simple keyword-overlap
    heuristic so this layer still produces a usable (if rougher) signal
    instead of silently skipping.

    Returns (supported_claims, unsupported_claims, avg_similarity_score).
    """
    if not claims:
        return [], [], 1.0

    if not retrieved_chunks:
        return [], list(claims), 0.0

    context_text = " ".join(chunk.text for chunk in retrieved_chunks)

    if embedding_client is not None:
        import math

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        chunk_embeddings = [embedding_client.embed(chunk.text) for chunk in retrieved_chunks]
        supported, unsupported, scores = [], [], []

        for claim in claims:
            claim_embedding = embedding_client.embed(claim)
            best_score = max(
                (cosine(claim_embedding, chunk_emb) for chunk_emb in chunk_embeddings),
                default=0.0,
            )
            scores.append(best_score)
            if best_score >= rules.GROUNDING_SIMILARITY_THRESHOLD:
                supported.append(claim)
            else:
                unsupported.append(claim)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        return supported, unsupported, avg_score

    # Placeholder path: crude keyword-overlap heuristic (no embedding client wired yet)
    # TODO: replace with real embedding_client from ai_system/providers/embedding_client.py
    context_words = set(context_text.lower().split())
    supported, unsupported, scores = [], [], []

    for claim in claims:
        claim_words = set(claim.lower().split())
        if not claim_words:
            continue
        overlap_ratio = len(claim_words & context_words) / len(claim_words)
        scores.append(overlap_ratio)
        if overlap_ratio >= rules.GROUNDING_SIMILARITY_THRESHOLD:
            supported.append(claim)
        else:
            unsupported.append(claim)

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return supported, unsupported, avg_score


# ============================================================
# Layer 3: LLM-as-a-Judge (Groq)
# ============================================================

_GROQ_CLIENT: Groq | None = None


def _get_groq_client() -> Groq:
    """Lazily creates a single shared Groq client using the module's own API key."""
    global _GROQ_CLIENT
    if _GROQ_CLIENT is None:
        from app.core.config import settings  # local import to avoid circular imports

        api_key = settings.GROQ_API_KEY_VALIDATION
        if not api_key:
            raise LLMJudgeError("GROQ_API_KEY_VALIDATION is not set in the environment")
        _GROQ_CLIENT = Groq(api_key=api_key)
    return _GROQ_CLIENT


def _llm_judge_check(
    user_question: str,
    retrieved_chunks: list[RetrievedChunk],
    draft_answer: str,
    model: str = "llama-3.3-70b-versatile",
) -> dict:
    """
    Calls Groq with the grounding judge prompt and parses the JSON response.
    Raises LLMJudgeError if the call fails or the response isn't valid JSON.
    """
    context_text = "\n\n".join(
        f"[chunk_id={chunk.chunk_id}] {chunk.text}" for chunk in retrieved_chunks
    )
    prompt = build_grounding_judge_prompt(
        user_question=user_question,
        retrieved_chunks=context_text,
        draft_answer=draft_answer,
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=800,
        )
        raw_content = response.choices[0].message.content.strip()
    except Exception as exc:  # network errors, auth errors, rate limits, etc.
        raise LLMJudgeError(f"Groq API call failed: {exc}") from exc

    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_content.strip(), flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMJudgeError(f"Judge did not return valid JSON: {exc}") from exc


# ============================================================
# Main entry point
# ============================================================

def check_hallucination(
    user_question: str,
    draft_answer: str,
    retrieved_chunks: list[RetrievedChunk],
    embedding_client=None,
    use_llm_judge: bool = True,
) -> HallucinationCheckResult:
    """
    Runs all 3 layers and combines them into a single HallucinationCheckResult.

    Design choice: rules + similarity always run (cheap). The LLM judge is the
    most expensive layer, so use_llm_judge lets callers (e.g. unit tests) skip
    it and rely on rules+similarity only.
    """
    context_text = " ".join(chunk.text for chunk in retrieved_chunks)
    reasons: list[str] = []

    # --- Layer 1 ---
    rule_reasons, forbidden_phrases = _rule_based_check(draft_answer, context_text)
    reasons.extend(rule_reasons)

    # --- Layer 2 ---
    claims = _split_into_claims(draft_answer)
    supported_claims, unsupported_claims, similarity_score = _similarity_check(
        claims, retrieved_chunks, embedding_client
    )

    # --- Layer 3 (optional / expensive) ---
    llm_judge_result: dict | None = None
    if use_llm_judge and retrieved_chunks:
        try:
            llm_judge_result = _llm_judge_check(user_question, retrieved_chunks, draft_answer)
        except LLMJudgeError as exc:
            reasons.append(f"LLM judge unavailable, falling back to rules+similarity: {exc}")

    # --- Combine all layers ---
    if llm_judge_result is not None:
        grounding_score = float(llm_judge_result.get("grounding_score", similarity_score))
        grounded = bool(llm_judge_result.get("grounded", grounding_score >= rules.GROUNDING_SIMILARITY_THRESHOLD))
        unsupported_claims = list(set(unsupported_claims) | set(llm_judge_result.get("unsupported_claims", [])))
        supported_claims = list(set(supported_claims) | set(llm_judge_result.get("supported_claims", [])))
        if llm_judge_result.get("reason"):
            reasons.append(f"LLM judge: {llm_judge_result['reason']}")
        suggested_action = HallucinationAction(llm_judge_result.get("suggested_action", "pass"))
    else:
        grounding_score = similarity_score
        grounded = grounding_score >= rules.GROUNDING_SIMILARITY_THRESHOLD and not forbidden_phrases

        if forbidden_phrases or unsupported_claims:
            suggested_action = HallucinationAction.REGENERATE
        elif grounding_score < 0.3:
            suggested_action = HallucinationAction.FALLBACK
        elif not grounded:
            suggested_action = HallucinationAction.RETRIEVE_MORE
        else:
            suggested_action = HallucinationAction.PASS

    return HallucinationCheckResult(
        grounded=grounded,
        grounding_score=max(0.0, min(1.0, grounding_score)),
        unsupported_claims=unsupported_claims,
        supported_claims=supported_claims,
        reasons=reasons,
        suggested_action=suggested_action,
    )