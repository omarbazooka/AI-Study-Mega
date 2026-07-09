import pytest
from app.ai_system.validation.output_validator import validate_output
from app.ai_system.validation.schemas import TaskType, HallucinationCheckResult, OutputAction, HallucinationAction

@pytest.fixture
def mock_grounded_result():
    return HallucinationCheckResult(grounded=True, grounding_score=1.0, suggested_action=HallucinationAction.PASS)

def test_chat_output_grounded(mock_grounded_result):
    result = validate_output(TaskType.CHAT, "This is a valid long enough answer.", mock_grounded_result)
    assert result.action == OutputAction.PASS
    assert result.valid is True

def test_output_empty(mock_grounded_result):
    result = validate_output(TaskType.CHAT, "   ", mock_grounded_result)
    assert len(result.format_errors) > 0

def test_quiz_data_correct_answer_not_in_options(mock_grounded_result):
    quiz = {
        "questions": [
            {
                "question": "A?",
                "options": ["B", "C"],
                "correct_answer": "D",
                "explanation": "Because"
            }
        ]
    }
    result = validate_output(TaskType.QUIZ, "JSON here", mock_grounded_result, quiz_data=quiz)
    assert len(result.format_errors) > 0
    assert any("correct_answer is not present" in err for err in result.format_errors)

def test_quiz_data_duplicate_options(mock_grounded_result):
    quiz = {
        "questions": [
            {
                "question": "A?",
                "options": ["B", "B"],
                "correct_answer": "B",
                "explanation": "Because"
            }
        ]
    }
    result = validate_output(TaskType.QUIZ, "JSON here", mock_grounded_result, quiz_data=quiz)
    assert len(result.format_errors) > 0
    assert any("duplicates" in err for err in result.format_errors)

def test_output_contains_system_leak(mock_grounded_result):
    result = validate_output(TaskType.CHAT, "My system prompt says I am a bot", mock_grounded_result)
    assert len(result.safety_errors) > 0
    assert any("system prompt" in err.lower() for err in result.safety_errors)
