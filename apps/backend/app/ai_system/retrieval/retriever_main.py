import time
from .context_builder import ContextBuilder
from .hybrid_search import HybridSearch
from .query_rewriter import QueryRewriter
from .reranker import RuleBasedReranker
from .retrieval_config import DEFAULT_RETRIEVAL_CONFIG, RetrievalConfig
from .retrieval_errors import RetrievalError
from .schemas import RetrievalRequest, RetrievalResult, RetrievalStatus, RetrievalTrace


class DocumentRetriever:
    def __init__(
        self,
        *,
        hybrid_search: HybridSearch,
        query_rewriter=None,
        reranker=None,
        context_builder=None,
        config: RetrievalConfig = DEFAULT_RETRIEVAL_CONFIG,
    ):
        self.hybrid_search = hybrid_search
        self.query_rewriter = query_rewriter or QueryRewriter()
        self.reranker = reranker or RuleBasedReranker()
        self.context_builder = context_builder or ContextBuilder()
        self.config = config

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        start = time.perf_counter()
        trace = RetrievalTrace()
        try:
            top_k = self.config.bounded_top_k(request.top_k)
            max_context_tokens = self.config.bounded_context_tokens(request.max_context_tokens)
            rewrite = self.query_rewriter.rewrite(request.query, intent=request.intent, filters=request.filters)

            if not rewrite.keywords and not rewrite.filters.as_repository_filter():
                return self.finish(RetrievalResult(
                    status=RetrievalStatus.NEEDS_CLARIFICATION,
                    rewritten_query=rewrite.semantic_query,
                    reason="Query is too vague for document-grounded retrieval",
                    trace=trace,
                ), start)

            # Define attempts to retry retrieval with relaxed thresholds inside the same document
            from .schemas import MetadataFilters
            attempts = [
                (self.config.similarity_threshold, self.config.candidate_k, True),         # Attempt 1: Standard (0.55 / limit 4)
                (0.40, self.config.candidate_k * 2, True),                                 # Attempt 2: Relaxed threshold (0.40 / limit 8)
                (0.25, self.config.candidate_k * 4, True),                                 # Attempt 3: Deep search threshold (0.25 / limit 16)
            ]

            # If user has strict filters, allow Attempt 3 with those filters stripped
            has_strict_filters = (
                rewrite.filters.page_number is not None
                or rewrite.filters.chapter is not None
                or rewrite.filters.section_title is not None
            )
            if has_strict_filters:
                attempts.append((0.20, self.config.candidate_k * 2, False))

            candidates = []
            trace.expanded = False

            for attempt_idx, (threshold, candidate_k, use_filters) in enumerate(attempts):
                if attempt_idx > 0:
                    trace.expanded = True

                filters_to_use = rewrite.filters if use_filters else MetadataFilters()

                hybrid = await self.hybrid_search.search(
                    user_id=request.user_id,
                    document_id=request.document_id,
                    semantic_query=rewrite.semantic_query,
                    keyword_query=rewrite.keyword_query,
                    filters=filters_to_use,
                    candidate_k=candidate_k,
                )

                # Filter chunks meeting this attempt's threshold
                attempt_candidates = [chunk for chunk in hybrid.chunks if chunk.score >= threshold]
                if attempt_candidates:
                    candidates = attempt_candidates
                    trace.vector_results = hybrid.vector_count
                    trace.keyword_results = hybrid.keyword_count
                    trace.hybrid_candidates = len(hybrid.chunks)
                    trace.vector_search_latency_ms = hybrid.vector_latency_ms
                    trace.keyword_search_latency_ms = hybrid.keyword_latency_ms
                    break

            if not candidates:
                return self.finish(RetrievalResult(
                    status=RetrievalStatus.NO_RELEVANT_CONTEXT,
                    rewritten_query=rewrite.semantic_query,
                    reason="No relevant chunks found above threshold",
                    trace=trace,
                ), start)

            if self.config.enable_reranker:
                reranked = self.reranker.rerank(
                    chunks=candidates,
                    query_terms=rewrite.keywords,
                    filters=rewrite.filters,
                    limit=top_k,
                )
                candidates = reranked.chunks
                trace.rerank_latency_ms = reranked.latency_ms
            else:
                candidates = candidates[:top_k]

            context = self.context_builder.build(chunks=candidates, max_context_tokens=max_context_tokens)
            trace.context_build_latency_ms = context.latency_ms
            trace.final_selected = len(context.chunks)

            if not context.chunks:
                return self.finish(RetrievalResult(
                    status=RetrievalStatus.NO_RELEVANT_CONTEXT,
                    rewritten_query=rewrite.semantic_query,
                    reason="Relevant chunks could not fit into context budget",
                    trace=trace,
                ), start)

            confidence = self.confidence(context.chunks[0].score, len(context.chunks), top_k)
            
            # Map Supabase RPC retrieval citations if missing or create standard citations
            from .schemas import Citation
            citations = []
            for c in context.chunks:
                citations.append(Citation(chunk_id=c.chunk_id, page_number=c.page_number or 1, section_title=c.section_title))

            return self.finish(RetrievalResult(
                status=RetrievalStatus.FOUND,
                confidence=confidence,
                rewritten_query=rewrite.semantic_query,
                chunks=context.chunks,
                context_text=context.context_text,
                citations=citations,
                trace=trace,
            ), start)

        except Exception as exc:
            return self.finish(RetrievalResult(status=RetrievalStatus.ERROR, reason=str(exc), trace=trace), start)

    def confidence(self, best_score, selected_count, top_k):
        coverage = min(selected_count / max(top_k, 1), 1.0)
        return round(min(max((best_score * 0.8) + (coverage * 0.2), 0.0), 1.0), 4)

    def finish(self, result, start):
        trace = result.trace.copy(update={"total_retrieval_latency_ms": int((time.perf_counter() - start) * 1000)})
        return result.copy(update={"trace": trace})


async def retrieve(request: RetrievalRequest, retriever: DocumentRetriever) -> RetrievalResult:
    return await retriever.retrieve(request)
