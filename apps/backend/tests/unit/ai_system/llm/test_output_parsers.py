import pytest
from app.ai_system.services.llm.output_parsers import OutputParser
from app.ai_system.services.llm.schemas import QuizSchema
from app.ai_system.services.llm.exceptions import JSONParsingException

def test_json_extraction():
    raw_markdown = "```json\n{\n  \"quiz_title\": \"Physics Quiz\",\n  \"difficulty\": \"easy\",\n  \"questions\": []\n}\n```"
    extracted = OutputParser.extract_json_string(raw_markdown)
    assert extracted.startswith("{")
    assert extracted.endswith("}")

def test_json_trailing_comma_cleaning():
    malformed = "{\"name\": \"test\", \"items\": [1, 2, 3,],}"
    cleaned = OutputParser.clean_json_content(malformed)
    assert cleaned == "{\"name\": \"test\", \"items\": [1, 2, 3]}"

def test_parse_quiz_success():
    raw = """
    ```json
    {
      "quiz_title": "Math Quiz",
      "difficulty": "medium",
      "questions": [
        {
          "question": "1+1?",
          "type": "mcq",
          "options": ["1", "2", "3", "4"],
          "correct_answer": "2",
          "explanation": "Simple arithmetic",
          "source_chunk_ids": ["c1"]
        }
      ]
    }
    ```
    """
    res = OutputParser.parse_quiz(raw)
    assert res.quiz_title == "Math Quiz"
    assert len(res.questions) == 1
    assert res.questions[0].correct_answer == "2"

def test_parse_quiz_invalid_options_count():
    # Only 3 options instead of 4
    raw = """
    {
      "quiz_title": "Math Quiz",
      "difficulty": "medium",
      "questions": [
        {
          "question": "1+1?",
          "type": "mcq",
          "options": ["1", "2", "3"],
          "correct_answer": "2",
          "explanation": "Invalid choices",
          "source_chunk_ids": ["c1"]
        }
      ]
    }
    """
    with pytest.raises(JSONParsingException):
        OutputParser.parse_quiz(raw)

def test_parse_quiz_correct_answer_not_in_options():
    # Correct answer is "5", which is not in options list
    raw = """
    {
      "quiz_title": "Math Quiz",
      "difficulty": "medium",
      "questions": [
        {
          "question": "1+1?",
          "type": "mcq",
          "options": ["1", "2", "3", "4"],
          "correct_answer": "5",
          "explanation": "Incorrect option match",
          "source_chunk_ids": ["c1"]
        }
      ]
    }
    """
    with pytest.raises(JSONParsingException):
        OutputParser.parse_quiz(raw)
