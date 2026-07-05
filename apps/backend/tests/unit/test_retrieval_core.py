import pytest

from app.ai_system.retrieval.context_builder import ContextBuilder
from app.ai_system.retrieval.hybrid_search import HybridSearch
from app.ai_system.retrieval.keyword_search import KeywordSearch
from app.ai_system.retrieval.query_rewriter import QueryRewriter
from app.ai_system.retrieval.retrieval_config import RetrievalConfig
from app.ai_system.retrieval.reranker import RuleBasedReranker
from app.ai_system.retrieval.schemas import MetadataFilters, RetrievedChunk


def chunk(chunk_id, text, score=0.5, page=1, section="Chapter 1"):
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="doc1",
        user_id="user1",
        text=text,
        score=score,
        vector_score=score,
        keyword_score=score,
        page_number=page,
        section_title=section,
    )


def test_query_rewrite_arabic_chapter():
    result = QueryRewriter().rewrite(chr(0x0627) + chr(0x0634) + chr(0x0631) + chr(0x062d) + " chapter 3")
    assert result.intent_hint == "explain"
    assert result.filters.chapter == "3"
    assert "chapter 3" in result.semantic_query


def test_query_rewrite_mixed_quiz():
    result = QueryRewriter().rewrite("Ø§Ø¹Ù…Ù„ quiz Ø¹Ù„Ù‰ Ø§Ù„ØªØ¹Ø±ÙŠÙØ§Øª")
    assert result.intent_hint == "quiz"
    assert "definitions" in result.semantic_query


def test_page_filter_extraction():
    result = QueryRewriter().rewrite("explain page 12")
    assert result.filters.page_number == 12


def test_context_builder_budget():
    chunks = [
        chunk("c1", " ".join(["important"] * 50), 0.9),
        chunk("c2", " ".join(["less"] * 500), 0.7),
    ]
    built = ContextBuilder().build(chunks=chunks, max_context_tokens=120)
    assert built.chunks
    assert "Chunk ID: c1" in built.context_text


def test_reranker_metadata_boost():
    chunks = [
        chunk("c1", "short", 0.5, page=2, section="Chapter 2"),
        chunk("c2", "this is a complete chunk about definitions and concepts", 0.5, page=5, section="Chapter 5"),
    ]
    ranked = RuleBasedReranker().rerank(
        chunks=chunks,
        query_terms=["definitions"],
        filters=MetadataFilters(page_number=5),
        limit=2,
    )
    assert ranked.chunks[0].chunk_id == "c2"
