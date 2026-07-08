"""
Wires the RAG retrieval module (hybrid search + rerank + context building) to the
project's real dependencies: the Supabase document_chunks repository and the
Cloudflare Workers AI embedding client.

This is the single integration point the orchestrator/pipeline layer should import
from, so that memory (app.ai_system.memory) and retrieval (app.ai_system.retrieval)
stay decoupled from each other and only meet inside the pipeline that calls both.

Imports of the real repository/embedding client are deliberately deferred to inside
the functions below (rather than at module load time), so that importing
app.ai_system.retrieval for unit tests does not require app.core.config/settings or
a configured Supabase client at all.
"""
from .hybrid_search import HybridSearch
from .keyword_search import KeywordSearch
from .retrieval_config import DEFAULT_RETRIEVAL_CONFIG, RetrievalConfig
from .retriever_main import DocumentRetriever
from .vector_store import VectorStore


class _EmbeddingClientAdapter:
    """Adapts providers.embedding_client.embed_query to VectorStore's EmbeddingClientProtocol."""

    def embed_query(self, text: str):
        from app.ai_system.providers.embedding_client import embed_query
        return embed_query(text)


_retriever_singleton: DocumentRetriever = None


def build_document_retriever(config: RetrievalConfig = DEFAULT_RETRIEVAL_CONFIG) -> DocumentRetriever:
    """Constructs a DocumentRetriever backed by the real document_chunks repository."""
    from app.db.repositories import chunk_repository

    vector_store = VectorStore(repository=chunk_repository, embedding_client=_EmbeddingClientAdapter())
    keyword_search = KeywordSearch(repository=chunk_repository)
    hybrid_search = HybridSearch(vector_store=vector_store, keyword_search=keyword_search, config=config)
    return DocumentRetriever(hybrid_search=hybrid_search, config=config)


def get_document_retriever() -> DocumentRetriever:
    """Returns a process-wide singleton DocumentRetriever (stateless, safe to share)."""
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = build_document_retriever()
    return _retriever_singleton
