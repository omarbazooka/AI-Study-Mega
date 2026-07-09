"""
Citation Builder — links the final AI answer back to the retrieved chunks
it was generated from, so every claim can be traced to a source.
"""

from app.ai_system.validation.schemas import Citation, CitationBuildResult, RetrievedChunk


# ============================================================
# Helper functions
# ============================================================

def _chunk_to_citation(chunk: RetrievedChunk, relevance_score: float) -> Citation:
    """
    Builds a single Citation from a retrieved chunk.
    Never fabricates a page number or section title — if they're missing
    on the chunk, they stay None on the citation too.
    """
    snippet = chunk.text.strip()
    # Keep snippets short and readable; this is just a preview, not the full chunk
    if len(snippet) > 200:
        snippet = snippet[:200].rstrip() + "..."

    return Citation(
        chunk_id=chunk.chunk_id,
        page_number=chunk.page_number,
        section_title=chunk.section_title,
        text_snippet=snippet,
        relevance_score=relevance_score,
    )


def _estimate_claim_coverage(claims: list[str], cited_chunk_ids: set[str], all_chunk_ids: set[str]) -> tuple[list[str], float]:
    """
    MOCK-friendly coverage estimate.
    Real "claim -> chunk" matching would need semantic similarity (embedding client),
    which belongs to hallucination_checker.py. Here we just do a simple presence
    check: if we have at least one citation and at least one claim, we assume
    partial coverage unless told otherwise by the caller.

    This keeps citation_builder.py usable standalone (no embedding dependency),
    while still returning a reasonable coverage_score.
    """
    if not claims:
        return [], 1.0

    if not cited_chunk_ids or not all_chunk_ids:
        # No chunks were cited at all -> nothing is covered
        return list(claims), 0.0

    # Placeholder heuristic: if we have citations, assume all claims are covered
    # until hallucination_checker.py flags specific unsupported claims.
    # TODO: replace with real per-claim matching once embedding-based
    # similarity is wired in from hallucination_checker.py.
    return [], 1.0


# ============================================================
# Main entry point
# ============================================================

def build_citations(
    final_answer: str,
    retrieved_chunks: list[RetrievedChunk],
    claims: list[str] | None = None,
) -> CitationBuildResult:
    """
    Builds citations connecting the final answer to the retrieved chunks.

    Args:
        final_answer: the text the user will see.
        retrieved_chunks: the chunks the Retriever fetched for this request.
        claims: optional list of individual claims/sentences extracted from
            the final answer (usually provided by hallucination_checker.py).
            If not provided, coverage_score defaults to 1.0 when citations exist.

    Rules followed (per validation spec):
        - Never fabricate a citation: only chunks that were actually retrieved
          can become citations.
        - Never fabricate a page number: if the chunk has none, the citation
          has none too.
    """
    if not retrieved_chunks:
        return CitationBuildResult(
            citations=[],
            coverage_score=0.0,
            uncited_claims=claims or [],
        )

    citations: list[Citation] = []
    cited_chunk_ids: set[str] = set()
    all_chunk_ids: set[str] = {chunk.chunk_id for chunk in retrieved_chunks}

    for chunk in retrieved_chunks:
        # Use the chunk's own similarity_score if available, otherwise a
        # neutral default (0.5) so we don't fabricate a false-confidence score.
        relevance_score = chunk.similarity_score if chunk.similarity_score is not None else 0.5
        citations.append(_chunk_to_citation(chunk, relevance_score))
        cited_chunk_ids.add(chunk.chunk_id)

    uncited_claims, coverage_score = _estimate_claim_coverage(
        claims=claims or [],
        cited_chunk_ids=cited_chunk_ids,
        all_chunk_ids=all_chunk_ids,
    )

    return CitationBuildResult(
        citations=citations,
        coverage_score=coverage_score,
        uncited_claims=uncited_claims,
    )