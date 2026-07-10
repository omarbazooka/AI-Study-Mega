from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from enum import Enum

class TaskType(str, Enum):
    CHAT_ANSWER = "chat_answer"
    EXPLAIN = "explain"
    SUMMARY = "summary"
    QUIZ = "quiz"
    KEY_POINTS = "key_points"
    COMPARISON_TABLE = "comparison_table"
    ANSWER_TABLE = "answer_table"
    FLASHCARDS = "flashcards"
    ANSWER_EVALUATION = "answer_evaluation"
    CLARIFICATION = "clarification"
    OUT_OF_SCOPE = "out_of_scope"
    UNKNOWN = "unknown"

class ExecutionMode(str, Enum):
    SINGLE = "single"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    HYBRID = "hybrid"

class ModelTier(str, Enum):
    RULE_BASED = "rule_based"
    LIGHTWEIGHT = "lightweight"
    REASONING = "reasoning"

class RetrievalStrategy(str, Enum):
    NONE = "none"
    VECTOR_TOP_K = "vector_top_k"
    HYBRID = "hybrid"
    MAP_REDUCE = "map_reduce"

class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    QUIZ_JSON = "quiz_json"
    FLASHCARDS_JSON = "flashcards_json"
    COMPARISON_TABLE_MARKDOWN = "comparison_table_markdown"
    ANSWER_TABLE_MARKDOWN = "answer_table_markdown"
    ANSWER_EVALUATION_JSON = "answer_evaluation_json"

class FallbackReason(str, Enum):
    NO_RELEVANT_CONTEXT = "no_relevant_context"
    VERIFICATION_FAILED = "verification_failed"
    PIPELINE_CRASH = "pipeline_crash"

class FallbackPolicy(BaseModel):
    allowed: bool = True
    fallback_text: str = "لم أجد إجابة واضحة في الملف المرفوع."
    reason: Optional[FallbackReason] = None

class VerificationPolicy(BaseModel):
    verify_grounding: bool = True
    verify_schema: bool = True
    verify_relevance: bool = True
    verify_completeness: bool = False
    max_retries: int = 2

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

class TraceStep(BaseModel):
    step_name: str
    status: str
    latency_ms: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PDFChatRequest(BaseModel):
    # user_id is optional so client-side can omit it; backend overrides/injects it internally
    user_id: Optional[str] = Field(None, description="Unique identifier for the user.")
    session_id: str = Field(..., min_length=1, description="Session identifier for thread tracking.")
    message: str = Field(..., min_length=1, max_length=1000, description="The user's query or instruction.")
    language: str = Field("ar", description="Language of response. Supported values: 'ar', 'en'.")
    user_level: str = Field("intermediate", description="Target educational level.")
    request_source: str = Field("chat", description="Origin of request (e.g., 'chat', 'summary_button', 'quiz_button').")
    document_id: Optional[str] = Field(None, description="The PDF document ID bound to the search.")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ["ar", "en"]:
            raise ValueError("Language must be 'ar' or 'en'.")
        return v

class SummaryRequest(BaseModel):
    # user_id is optional so client-side can omit it; backend overrides/injects it internally
    user_id: Optional[str] = Field(None, description="Unique identifier for the user.")
    session_id: str = Field(..., min_length=1, description="Session identifier for thread tracking.")
    language: str = Field("ar", description="Language of response. Supported values: 'ar', 'en'.")
    user_level: str = Field("intermediate", description="Target educational level.")
    summary_style: Optional[str] = Field(None, description="Style of summary (e.g., 'bullet_points', 'paragraph').")
    document_id: Optional[str] = Field(None, description="The PDF document ID bound to the summary.")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ["ar", "en"]:
            raise ValueError("Language must be 'ar' or 'en'.")
        return v

class QuizRequest(BaseModel):
    # user_id is optional so client-side can omit it; backend overrides/injects it internally
    user_id: Optional[str] = Field(None, description="Unique identifier for the user.")
    session_id: str = Field(..., min_length=1, description="Session identifier for thread tracking.")
    language: str = Field("ar", description="Language of response. Supported values: 'ar', 'en'.")
    user_level: str = Field("intermediate", description="Target educational level.")
    difficulty: Optional[str] = Field("medium", description="Difficulty level: 'easy', 'medium', 'hard'.")
    number_of_questions: Optional[int] = Field(5, description="Number of questions (1-20).")
    question_type: Optional[str] = Field("multiple_choice", description="Question format: 'multiple_choice', 'true_false', 'short_answer', 'mixed'.")
    document_id: Optional[str] = Field(None, description="The PDF document ID bound to the quiz.")

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
    type: TaskType
    query: str
    depends_on: List[str] = Field(default_factory=list)
    retrieval_required: bool = True
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    output_format: OutputFormat = OutputFormat.MARKDOWN
    model_tier: ModelTier = ModelTier.LIGHTWEIGHT
    verification_required: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DAGPlan(BaseModel):
    plan_id: str
    primary_intent: TaskType
    execution_mode: ExecutionMode
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    tasks: List[Task] = Field(default_factory=list)
    fallback_policy: FallbackPolicy = Field(default_factory=FallbackPolicy)
    verification_policy: VerificationPolicy = Field(default_factory=VerificationPolicy)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Alias ExecutionPlan for backwards compatibility
ExecutionPlan = DAGPlan

class Citation(BaseModel):
    chunk_id: str
    page_number: int
    section_title: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None

class TaskResult(BaseModel):
    task_id: str
    type: TaskType
    status: str  # success, failed, partial, needs_clarification, no_answer
    content: Any
    citations: List[Citation] = Field(default_factory=list)
    confidence: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AIResponse(BaseModel):
    status: str  # success, failed, partial, needs_clarification, no_answer
    message: str
    execution_mode: ExecutionMode
    tasks: List[TaskResult] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    confidence: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pipeline_trace: Optional[Dict[str, Any]] = None
