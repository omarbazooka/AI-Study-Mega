import time
from typing import Any, Dict, List, Protocol
from .retrieval_errors import VectorSearchError
from .schemas import MetadataFilters, RetrievedChunk


class EmbeddingClientProtocol(Protocol):
    def embed_query(self, text: str) -> List[float]:
        ...


class VectorChunkRepositoryProtocol(Protocol):
    def search_vector_chunks(
        self, *, user_id: str, document_id: str, query_embedding: List[float],
        match_count: int, filters: Dict[str, Any], similarity_threshold: float
    ) -> List[Dict[str, Any]]:
        ...


class VectorSearchResult:
    def __init__(self, chunks, latency_ms):
        self.chunks = chunks
        self.latency_ms = latency_ms


class VectorStore:
    def __init__(self, repository: VectorChunkRepositoryProtocol, embedding_client: EmbeddingClientProtocol):
        self.repository = repository
        self.embedding_client = embedding_client

    def search(self, *, user_id, document_id, query, match_count, filters: MetadataFilters, similarity_threshold):
        start = time.perf_counter()
        try:
            embedding = self.embedding_client.embed_query(query)
            rows = self.repository.search_vector_chunks(
                user_id=user_id,
                document_id=document_id,
                query_embedding=embedding,
                match_count=match_count,
                filters=filters.as_repository_filter(),
                similarity_threshold=similarity_threshold,
            )
            return VectorSearchResult(
                [self.row_to_chunk(row, user_id, document_id) for row in rows],
                int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:
            raise VectorSearchError(str(exc)) from exc

    def row_to_chunk(self, row, user_id, document_id):
        metadata = dict(row.get("metadata") or {})
        page = row.get("page_number") or metadata.get("page_number")
        section = row.get("section_title") or metadata.get("section_title")
        score = float(row.get("score", row.get("similarity", 0.0)) or 0.0)
        return RetrievedChunk(
            chunk_id=str(row.get("chunk_id") or row.get("id")),
            document_id=str(row.get("document_id") or document_id),
            user_id=str(row.get("user_id") or user_id),
            text=str(row.get("text") or row.get("raw_text") or row.get("content") or ""),
            score=score,
            vector_score=score,
            page_number=int(page) if page is not None else None,
            section_title=str(section) if section else None,
            chunk_index=row.get("chunk_index"),
            metadata=metadata,
        )
