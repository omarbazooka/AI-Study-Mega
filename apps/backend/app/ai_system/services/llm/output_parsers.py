import json
import re
import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from .exceptions import JSONParsingException
from .schemas import QuizSchema, AnswerEvaluationSchema

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class OutputParser:
    """Utility class to clean, parse, and validate JSON outputs from LLMs."""

    @staticmethod
    def extract_json_string(text: str) -> str:
        """Extracts JSON blocks from markdown wrappers or outer braces."""
        text = text.strip()

        # Extract markdown json blocks
        markdown_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if markdown_match:
            return markdown_match.group(1).strip()

        # Find first '{' or '[' and matching last '}' or ']'
        brace_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if brace_match:
            return brace_match.group(1).strip()

        return text

    @staticmethod
    def clean_json_content(json_str: str) -> str:
        """Applies heuristics to repair trailing commas in JSON."""
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r",\s*(\}|\])", r"\1", json_str)
        return json_str

    @classmethod
    def parse_and_validate(cls, raw_output: str, schema: Type[T]) -> T:
        """
        Parses raw text as JSON and validates it against the provided Pydantic model.
        Raises JSONParsingException on failure.
        """
        extracted = cls.extract_json_string(raw_output)
        cleaned = cls.clean_json_content(extracted)

        try:
            parsed_dict = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding failed on extracted string: {cleaned[:300]}...")
            raise JSONParsingException(
                raw_output, 
                f"JSON Decode Error: {e.msg} at line {e.lineno} column {e.colno}"
            )

        try:
            return schema.model_validate(parsed_dict)
        except ValidationError as e:
            logger.error(f"Pydantic validation failed: {str(e)}")
            raise JSONParsingException(raw_output, f"Validation Error: {str(e)}")

    @classmethod
    def parse_quiz(cls, raw_output: str) -> QuizSchema:
        """Parses and validates output as a QuizSchema."""
        return cls.parse_and_validate(raw_output, QuizSchema)

    @classmethod
    def parse_evaluation(cls, raw_output: str) -> AnswerEvaluationSchema:
        """Parses and validates output as an AnswerEvaluationSchema."""
        return cls.parse_and_validate(raw_output, AnswerEvaluationSchema)
