import pytest
from app.ai_system.validation.verifier import verify_response
from app.ai_system.validation.schemas import TaskType, RetrievedChunk, VerifierAction
from app.ai_system.validation.rules import FALLBACK_MESSAGE, MAX_VERIFICATION_RETRIES

@pytest.fixture
def sample_chunks():
    return [RetrievedChunk(chunk_id="c1", text="A chunk of text", similarity_score=0.9)]

def test_verifier_empty_chunks():
    result = verify_response("query", TaskType.CHAT, [], "output", use_llm_judge=False)
    assert result.action == VerifierAction.FALLBACK
    assert result.final_answer == FALLBACK_MESSAGE

def test_verifier_max_retries_exceeded(sample_chunks):
    result = verify_response("query", TaskType.CHAT, sample_chunks, "output", retry_count=MAX_VERIFICATION_RETRIES + 1, use_llm_judge=False)
    assert result.action == VerifierAction.FALLBACK

def test_verifier_all_valid(sample_chunks, monkeypatch):
    # Mock check_hallucination to avoid any actual processing or Groq calls
    def mock_check_hallucination(*args, **kwargs):
        from app.ai_system.validation.schemas import HallucinationCheckResult, HallucinationAction
        return HallucinationCheckResult(grounded=True, grounding_score=1.0, suggested_action=HallucinationAction.PASS)
    
    monkeypatch.setattr("app.ai_system.validation.verifier.check_hallucination", mock_check_hallucination)
    
    result = verify_response("query", TaskType.CHAT, sample_chunks, "This is a properly grounded and long enough output.")
    assert result.passed is True
    assert result.action == VerifierAction.RETURN
