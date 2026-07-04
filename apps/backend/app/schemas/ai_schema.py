from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional

class PDFChatRequest(BaseModel):
    # TODO: user_id is temporary and should later come from authenticated user context
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user.")
    session_id: str = Field(..., min_length=1, description="Session identifier for thread tracking.")
    message: str = Field(..., min_length=1, max_length=1000, description="The user's query or instruction.")
    language: str = Field("ar", description="Language of response. Supported values: 'ar', 'en'.")
    user_level: str = Field("intermediate", description="Target educational level.")
    request_source: str = Field("chat", description="Origin of request (e.g., 'chat', 'summary_button', 'quiz_button').")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ["ar", "en"]:
            raise ValueError("Language must be 'ar' or 'en'.")
        return v

class SummaryRequest(BaseModel):
    # TODO: user_id is temporary and should later come from authenticated user context
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user.")
    session_id: str = Field(..., min_length=1, description="Session identifier for thread tracking.")
    language: str = Field("ar", description="Language of response. Supported values: 'ar', 'en'.")
    user_level: str = Field("intermediate", description="Target educational level.")
    summary_style: Optional[str] = Field(None, description="Style of summary (e.g., 'bullet_points', 'paragraph').")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ["ar", "en"]:
            raise ValueError("Language must be 'ar' or 'en'.")
        return v

class QuizRequest(BaseModel):
    # TODO: user_id is temporary and should later come from authenticated user context
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user.")
    session_id: str = Field(..., min_length=1, description="Session identifier for thread tracking.")
    language: str = Field("ar", description="Language of response. Supported values: 'ar', 'en'.")
    user_level: str = Field("intermediate", description="Target educational level.")
    difficulty: Optional[str] = Field("medium", description="Difficulty level: 'easy', 'medium', 'hard'.")
    number_of_questions: Optional[int] = Field(5, description="Number of questions (1-20).")
    question_type: Optional[str] = Field("multiple_choice", description="Question format: 'multiple_choice', 'true_false', 'short_answer', 'mixed'.")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ["ar", "en"]:
            raise ValueError("Language must be 'ar' or 'en'.")
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["easy", "medium", "hard"]:
            raise ValueError("Difficulty must be 'easy', 'medium', or 'hard'.")
        return v

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["multiple_choice", "true_false", "short_answer", "mixed"]:
            raise ValueError("Question type must be 'multiple_choice', 'true_false', 'short_answer', or 'mixed'.")
        return v

    @field_validator("number_of_questions")
    @classmethod
    def validate_num_questions(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 20):
            raise ValueError("Number of questions must be between 1 and 20.")
        return v

class Task(BaseModel):
    task_id: str
    type: str  # chat_answer, explain, summary, quiz, answer_table, key_points, comparison_table, unknown
    query: str
    depends_on: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExecutionPlan(BaseModel):
    execution_mode: str  # single, parallel, sequential
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    tasks: List[Task] = Field(default_factory=list)

class Citation(BaseModel):
    chunk_id: str
    page_number: int
    section_title: Optional[str] = None
    score: Optional[float] = None

class TaskResult(BaseModel):
    task_id: str
    type: str
    status: str  # success, failed, partial, needs_clarification, no_answer
    content: Any
    citations: List[Citation] = Field(default_factory=list)
    confidence: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AIResponse(BaseModel):
    status: str  # success, failed, partial, needs_clarification, no_answer
    message: str
    execution_mode: str
    tasks: List[TaskResult] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    confidence: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
