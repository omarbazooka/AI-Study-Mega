from .keyword_search import KeywordSearch
from .retrieval_config import RetrievalConfig
from .schemas import MetadataFilters
from .vector_store import VectorStore


class HybridSearchResult:
    def __init__(self, chunks, vector_count, keyword_count, vector_latency_ms, keyword_latency_ms):
        self.chunks = chunks
        self.vector_count = vector_count
        self.keyword_count = keyword_count
        self.vector_latency_ms = vector_latency_ms
        self.keyword_latency_ms = keyword_latency_ms


class HybridSearch:
    def __init__(self, vector_store: VectorStore, keyword_search: KeywordSearch, config: RetrievalConfig):
        self.vector_store = vector_store
        self.keyword_search = keyword_search
        self.config = config

    def search(self, *, user_id, document_id, semantic_query, keyword_query, filters: MetadataFilters, candidate_k=None):
        match_count = candidate_k or self.config.candidate_k
        vector = self.vector_store.search(
            user_id=user_id, document_id=document_id, query=semantic_query,
            match_count=match_count, filters=filters,
            similarity_threshold=self.config.similarity_threshold,
        )
        keyword = self.keyword_search.search(
            user_id=user_id, document_id=document_id, query=keyword_query,
            match_count=match_count, filters=filters,
        )
        return HybridSearchResult(
            self.merge(vector.chunks, keyword.chunks, filters),
            len(vector.chunks),
            len(keyword.chunks),
            vector.latency_ms,
            keyword.latency_ms,
        )

    def merge(self, vector_chunks, keyword_chunks, filters):
        merged = {}
        for chunk, score in self.normalize(vector_chunks, "vector_score"):
            merged[chunk.chunk_id] = chunk.copy(update={"vector_score": score})
        for chunk, score in self.normalize(keyword_chunks, "keyword_score"):
            if chunk.chunk_id in merged:
                old = merged[chunk.chunk_id]
                merged[chunk.chunk_id] = old.copy(update={"keyword_score": score})
            else:
                merged[chunk.chunk_id] = chunk.copy(update={"keyword_score": score})

        ranked = []
        for chunk in merged.values():
            metadata_score = self.metadata_score(chunk, filters)
            final_score = (
                self.config.vector_weight * chunk.vector_score
                + self.config.keyword_weight * chunk.keyword_score
                + self.config.metadata_weight * metadata_score
            )
            ranked.append(chunk.copy(update={"metadata_score": metadata_score, "score": round(final_score, 6)}))
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def normalize(self, chunks, field):
        if not chunks:
            return []
        scores = [float(getattr(chunk, field) or chunk.score or 0.0) for chunk in chunks]
        max_score = max(scores) or 1.0
        return [(chunk, max(0.0, min(score / max_score, 1.0))) for chunk, score in zip(chunks, scores)]

    def metadata_score(self, chunk, filters):
        score = 0.0
        checks = 0
        if filters.page_number is not None:
            checks += 1
            score += 1.0 if chunk.page_number == filters.page_number else 0.0
        if filters.section_title:
            checks += 1
            score += 1.0 if filters.section_title.lower() in (chunk.section_title or "").lower() else 0.0
        if filters.chapter:
            checks += 1
            wanted = filters.chapter.lower()
            section = (chunk.section_title or "").lower()
            metadata_chapter = str(chunk.metadata.get("chapter", "")).lower()
            score += 1.0 if wanted in section or wanted == metadata_chapter else 0.0
        return score / checks if checks else 0.0
