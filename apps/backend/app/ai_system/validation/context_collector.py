import logging
from typing import List, Dict, Any, Optional
from app.ai_system.validation.schemas import ExecutionStrategy, RetrievedChunk

logger = logging.getLogger(__name__)

async def collect_context(
    strategy: ExecutionStrategy,
    query: str,
    document_id: str,
    user_id: str,
    request: Optional[Any] = None
) -> List[RetrievedChunk]:
    """
    Collects context according to the specified context collection strategy.
    Implements focused_retrieval, section_coverage_retrieval, full_document_context,
    and map_reduce_analysis.
    """
    from app.db.repositories import chunk_repository
    from app.ai_system.retrieval import get_document_retriever
    from app.ai_system.retrieval.schemas import RetrievalRequest, RetrievalStatus

    # Default metadata lookup skips chunk retrieval entirely
    if strategy == ExecutionStrategy.metadata_lookup:
        return []

    # 1. focused_retrieval strategy: semantic & keyword fusion
    if strategy == ExecutionStrategy.focused_retrieval or not strategy:
        retriever = get_document_retriever()
        res = await retriever.retrieve(RetrievalRequest(
            user_id=user_id,
            document_id=document_id,
            query=query
        ))
        
        if request is not None:
            request._retrieval_result = res
            
        chunks = []
        if res.status == RetrievalStatus.FOUND:
            for idx, c in enumerate(res.chunks):
                chunks.append(RetrievedChunk(
                    chunk_id=c.chunk_id,
                    text=c.text,
                    document_id=document_id,
                    page_number=c.page_number or 1,
                    section_title=c.section_title or "Focused Retrieval",
                    similarity_score=c.score or (1.0 - 0.05 * idx)
                ))
        return chunks

    # 2. full_document_context strategy: gathers all document chunks
    elif strategy == ExecutionStrategy.full_document_context or strategy == ExecutionStrategy.transformation_pipeline:
        db_chunks = await chunk_repository.get_chunks_by_document(document_id)
        chunks = []
        for idx, c in enumerate(db_chunks):
            # Check size limits so we don't overflow token window (safe limit of 50 chunks max)
            if idx >= 50:
                break
            chunks.append(RetrievedChunk(
                chunk_id=c.get("id") or str(c.get("chunk_index", idx)),
                text=c.get("content", ""),
                document_id=document_id,
                page_number=c.get("page_start") or 1,
                section_title=c.get("section_title") or f"Page {c.get('page_start')}",
                similarity_score=1.0
            ))
        return chunks

    # 3. section_coverage_retrieval strategy: gets one representative chunk per page
    elif strategy == ExecutionStrategy.section_coverage_retrieval:
        db_chunks = await chunk_repository.get_chunks_by_document(document_id)
        pages_seen = set()
        chunks = []
        for idx, c in enumerate(db_chunks):
            page = c.get("page_start") or 1
            if page not in pages_seen:
                pages_seen.add(page)
                chunks.append(RetrievedChunk(
                    chunk_id=c.get("id") or str(c.get("chunk_index", idx)),
                    text=c.get("content", ""),
                    document_id=document_id,
                    page_number=page,
                    section_title=c.get("section_title") or f"Section {page}",
                    similarity_score=0.9
                ))
                # Max 15 pages for section coverage
                if len(chunks) >= 15:
                    break
        return chunks

    # 4. map_reduce_analysis: gathers all chunks, to be mapped/reduced in the executor
    elif strategy == ExecutionStrategy.map_reduce_analysis:
        db_chunks = await chunk_repository.get_chunks_by_document(document_id)
        chunks = []
        for idx, c in enumerate(db_chunks):
            if idx >= 60:  # Map-Reduce limit of 60 chunks
                break
            chunks.append(RetrievedChunk(
                chunk_id=c.get("id") or str(c.get("chunk_index", idx)),
                text=c.get("content", ""),
                document_id=document_id,
                page_number=c.get("page_start") or 1,
                section_title=c.get("section_title") or f"Page {c.get('page_start')}",
                similarity_score=1.0
            ))
        return chunks

    return []
