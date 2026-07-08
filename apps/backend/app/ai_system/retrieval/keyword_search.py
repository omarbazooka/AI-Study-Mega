import inspect
import time
from typing import Any, Dict, List, Protocol
from .retrieval_errors import KeywordSearchError
from .schemas import MetadataFilters, RetrievedChunk


class KeywordChunkRepositoryProtocol(Protocol):
    async def search_keyword_chunks(
        self, *, user_id: str, document_id: str, query: str,
        match_count: int, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        ...


class KeywordSearchResult:
    def __init__(self, chunks, latency_ms):
        self.chunks = chunks
        self.latency_ms = latency_ms


class KeywordSearch:
    def __init__(self, repository: KeywordChunkRepositoryProtocol):
        self.repository = repository

    async def search(self, *, user_id, document_id, query, match_count, filters: MetadataFilters):
        start = time.perf_counter()
        try:
            if not query.strip():
                return KeywordSearchResult([], 0)
            rows = self.repository.search_keyword_chunks(
                user_id=user_id,
                document_id=document_id,
                query=query,
                match_count=match_count,
                filters=filters.as_repository_filter(),
            )
            if inspect.isawaitable(rows):
                rows = await rows
            rows = [row for row in rows if row]
            return KeywordSearchResult(
                [self.row_to_chunk(row, user_id, document_id) for row in rows],
                int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:
            raise KeywordSearchError(str(exc)) from exc

    def row_to_chunk(self, row, user_id, document_id):
        metadata = dict(row.get("metadata") or {})
        page = row.get("page_number") or row.get("page_start") or metadata.get("page_number") or metadata.get("page_start")
        section = row.get("section_title") or metadata.get("section_title")
        score = float(row.get("score", row.get("rank", 0.0)) or 0.0)
        return RetrievedChunk(
            chunk_id=str(row.get("chunk_id") or row.get("id")),
            document_id=str(row.get("document_id") or document_id),
            user_id=str(row.get("user_id") or user_id),
            text=str(row.get("text") or row.get("raw_text") or row.get("content") or ""),
            score=score,
            keyword_score=score,
            page_number=int(page) if page is not None else None,
            section_title=str(section) if section else None,
            chunk_index=row.get("chunk_index"),
            metadata=metadata,
        )
