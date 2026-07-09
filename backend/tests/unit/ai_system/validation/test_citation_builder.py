import pytest
from app.ai_system.validation.citation_builder import build_citations
from app.ai_system.validation.schemas import RetrievedChunk

@pytest.fixture
def sample_chunks():
    return [
        RetrievedChunk(chunk_id="c1", text="Chunk 1 text", page_number=1, similarity_score=0.9),
        RetrievedChunk(chunk_id="c2", text="Chunk 2 text", section_title="Intro", similarity_score=0.8)
    ]

def test_build_citations_with_chunks(sample_chunks):
    result = build_citations("Final answer", sample_chunks)
    assert len(result.citations) == 2
    assert result.coverage_score == 1.0

def test_build_citations_empty_chunks():
    result = build_citations("Final answer", [])
    assert len(result.citations) == 0
    assert result.coverage_score == 0.0

def test_citation_page_number_none_when_missing(sample_chunks):
    result = build_citations("Final answer", sample_chunks)
    assert result.citations[0].page_number == 1
    assert result.citations[1].page_number is None
