import pytest
from app.ai_system.validation.hallucination_checker import check_hallucination
from app.ai_system.validation.schemas import RetrievedChunk

@pytest.fixture
def sample_chunks():
    return [
        RetrievedChunk(chunk_id="c1", text="Python is a programming language created in 1991.")
    ]

@pytest.mark.asyncio
async def test_hallucination_fully_grounded(monkeypatch, sample_chunks):
    async def mock_llm_judge(*args, **kwargs):
        return {
            "grounded": True,
            "grounding_score": 1.0,
            "suggested_action": "pass"
        }
    monkeypatch.setattr("app.ai_system.validation.hallucination_checker._llm_judge_check", mock_llm_judge)
    
    result = await check_hallucination("What is Python?", "Python is a programming language.", sample_chunks)
    assert result.grounded is True

@pytest.mark.asyncio
async def test_hallucination_with_unsupported_number(monkeypatch, sample_chunks):
    async def mock_llm_judge(*args, **kwargs):
        return {"grounded": False, "grounding_score": 0.5, "suggested_action": "regenerate"}
    monkeypatch.setattr("app.ai_system.validation.hallucination_checker._llm_judge_check", mock_llm_judge)

    # 1995 is not in context (1991 is)
    result = await check_hallucination("When was it created?", "Created in 1995.", sample_chunks)
    assert any("1995" in reason for reason in result.reasons)

@pytest.mark.asyncio
async def test_hallucination_with_forbidden_phrase(monkeypatch, sample_chunks):
    async def mock_llm_judge(*args, **kwargs):
        return {"grounded": False, "grounding_score": 0.5, "suggested_action": "regenerate"}
    monkeypatch.setattr("app.ai_system.validation.hallucination_checker._llm_judge_check", mock_llm_judge)

    result = await check_hallucination("Tell me", "Generally speaking, it is good.", sample_chunks)
    assert any("generally speaking" in reason.lower() for reason in result.reasons)

@pytest.mark.asyncio
async def test_use_llm_judge_false_runs_without_groq(sample_chunks):
    # Pass use_llm_judge=False so it doesn't call Groq. If it does, Groq without mock will fail.
    result = await check_hallucination("What is Python?", "Python is a programming language.", sample_chunks, use_llm_judge=False)
    assert result.grounded is True
