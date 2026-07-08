import pytest
from app.ai_system.retrieval.hybrid_search import HybridSearch
from app.ai_system.retrieval.keyword_search import KeywordSearch
from app.ai_system.retrieval.retrieval_config import RetrievalConfig
from app.ai_system.retrieval.retriever_main import DocumentRetriever
from app.ai_system.retrieval.schemas import RetrievalRequest, RetrievalStatus
from app.ai_system.retrieval.vector_store import VectorStore


class FakeEmbedding:
    def embed_query(self, text):
        return [0.1, 0.2, 0.3]


class FakeRepo:
    def __init__(self):
        self.rows = [
            {
                "id": "c1",
                "document_id": "doc1",
                "user_id": "user1",
                "raw_text": "Photosynthesis converts light energy into chemical energy in plants.",
                "score": 0.92,
                "page_number": 4,
                "section_title": "Chapter 2",
                "metadata": {"chapter": "2"},
            },
            {
                "id": "c2",
                "document_id": "doc2",
                "user_id": "user2",
                "raw_text": "This belongs to another user and must not leak.",
                "score": 0.99,
            },
        ]

    def search_vector_chunks(self, *, user_id, document_id, query_embedding, match_count, filters, similarity_threshold):
        return [
            row for row in self.rows
            if row["user_id"] == user_id
            and row["document_id"] == document_id
            and row.get("score", 0) >= similarity_threshold
        ][:match_count]

    def search_keyword_chunks(self, *, user_id, document_id, query, match_count, filters):
        terms = query.lower().split()
        return [
            row for row in self.rows
            if row["user_id"] == user_id
            and row["document_id"] == document_id
            and any(term in row["raw_text"].lower() for term in terms)
        ][:match_count]


def build_retriever(threshold=0.35):
    repo = FakeRepo()
    config = RetrievalConfig(similarity_threshold=threshold)
    vector = VectorStore(repo, FakeEmbedding())
    keyword = KeywordSearch(repo)
    hybrid = HybridSearch(vector, keyword, config)
    return DocumentRetriever(hybrid_search=hybrid, config=config)


@pytest.mark.asyncio
async def test_retrieves_known_answer_and_citation():
    retriever = build_retriever()
    result = await retriever.retrieve(RetrievalRequest(user_id="user1", document_id="doc1", query="explain photosynthesis"))
    assert result.status == RetrievalStatus.FOUND
    assert result.chunks[0].chunk_id == "c1"
    assert result.citations[0].page_number == 4


@pytest.mark.asyncio
async def test_user_isolation():
    retriever = build_retriever()
    result = await retriever.retrieve(RetrievalRequest(user_id="user1", document_id="doc1", query="another user"))
    assert all(chunk.user_id == "user1" for chunk in result.chunks)


@pytest.mark.asyncio
async def test_no_relevant_context():
    retriever = build_retriever(threshold=0.98)
    result = await retriever.retrieve(RetrievalRequest(user_id="user1", document_id="doc1", query="unrelated"))
    assert result.status == RetrievalStatus.NO_RELEVANT_CONTEXT
