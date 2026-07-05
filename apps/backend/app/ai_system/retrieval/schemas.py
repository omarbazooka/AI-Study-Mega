from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class RetrievalStatus(str, Enum):
    FOUND = "FOUND"
    NO_RELEVANT_CONTEXT = "NO_RELEVANT_CONTEXT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    ERROR = "ERROR"


class MetadataFilters(BaseModel):
    page_number: Optional[int] = None
    chapter: Optional[str] = None
    section_title: Optional[str] = None
    intent_hint: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    def as_repository_filter(self) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if self.page_number is not None:
            filters["page_number"] = self.page_number
        if self.chapter:
            filters["chapter"] = self.chapter
        if self.section_title:
            filters["section_title"] = self.section_title
        filters.update(self.extra)
        return filters


class QueryRewriteResult(BaseModel):
    original_query: str
    normalized_query: str
    semantic_query: str
    keyword_query: str
    keywords: List[str] = Field(default_factory=list)
    filters: MetadataFilters = Field(default_factory=MetadataFilters)
    intent_hint: Optional[str] = None


class RetrievalRequest(BaseModel):
    user_id: str
    document_id: str
    query: str
    intent: Optional[str] = None
    top_k: Optional[int] = None
    max_context_tokens: Optional[int] = None
    filters: MetadataFilters = Field(default_factory=MetadataFilters)

    @validator("user_id", "document_id", "query")
    def required(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    user_id: str
    text: str
    score: float = 0.0
    vector_score: float = 0.0
    keyword_score: float = 0.0
    metadata_score: float = 0.0
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    chunk_index: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    chunk_id: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None


class RetrievalTrace(BaseModel):
    vector_results: int = 0
    keyword_results: int = 0
    hybrid_candidates: int = 0
    final_selected: int = 0
    vector_search_latency_ms: int = 0
    keyword_search_latency_ms: int = 0
    rerank_latency_ms: int = 0
    context_build_latency_ms: int = 0
    total_retrieval_latency_ms: int = 0


class RetrievalResult(BaseModel):
    status: RetrievalStatus
    confidence: float = 0.0
    rewritten_query: Optional[str] = None
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    context_text: str = ""
    citations: List[Citation] = Field(default_factory=list)
    trace: RetrievalTrace = Field(default_factory=RetrievalTrace)
    reason: Optional[str] = None
