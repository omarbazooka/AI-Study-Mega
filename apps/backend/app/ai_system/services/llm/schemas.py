from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

# Structured LLM Output Schemas

class QuizQuestionSchema(BaseModel):
    question: str = Field(description="The question prompt")
    type: Literal["mcq"] = Field("mcq", description="The type of the question, currently multiple-choice")
    options: List[str] = Field(description="List of exactly 4 potential options")
    correct_answer: str = Field(description="The exact text of the correct option")
    explanation: str = Field(description="Step-by-step educational reason why this is correct")
    source_chunk_ids: List[str] = Field(description="Chunk IDs from the context used to construct this question")

class QuizSchema(BaseModel):
    quiz_title: str = Field(description="Title of the quiz")
    difficulty: Literal["easy", "medium", "hard"] = Field(description="Difficulty level")
    questions: List[QuizQuestionSchema] = Field(description="List of questions in the quiz")

class AnswerEvaluationSchema(BaseModel):
    score: int = Field(default=0, ge=0, le=100, description="Grade from 0 to 100")
    status: Literal["correct", "partially_correct", "incorrect"] = Field(description="Grading status classification")
    missing_points: List[str] = Field(description="Crucial concepts or key details the student missed")
    mistake_analysis: str = Field(description="Detailed analysis of student misconceptions")
    correct_answer: str = Field(description="Detailed reference answer based strictly on context")
    explanation: str = Field(description="Explanation of grading and reasoning")
    source_chunk_ids: List[str] = Field(description="Chunk IDs supporting the evaluation")

class VerifierSchema(BaseModel):
    is_grounded: bool = Field(description="True if the text is fully grounded, False if there are hallucinations")
    reason: str = Field(description="Detailed explanation of the grounding check")


# Inputs Payloads Sent to LLM Engineer

class ChunkContext(BaseModel):
    chunk_id: str
    page_number: Optional[int] = None
    score: Optional[float] = None
    content: str

class MemoryContext(BaseModel):
    rule: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_style: Optional[str] = None
    difficulty: Optional[str] = None
    quiz_difficulty: Optional[str] = None
    include_examples: Optional[bool] = None
    include_answer_key: Optional[bool] = None
    dyslexia_friendly: Optional[bool] = None
    recent_context_summary: Optional[str] = None

class StrictGroundingPolicy(BaseModel):
    academic_source_of_truth: str
    memory_usage: str
    if_document_context_insufficient: str = "لم أجد إجابة واضحة في الملف المرفوع."

class ExpectedLLMOutputFormat(BaseModel):
    type: str
    style: Optional[str] = None
    question_count: Optional[int] = None
    question_type: Optional[str] = None
    must_be_grounded: bool = True
    must_not_use_general_knowledge: bool = True
    must_include_source_chunk_id_per_question: Optional[bool] = None

class SourceInfo(BaseModel):
    source_id: str
    source_type: str
    scope_filter: Optional[Dict[str, Any]] = None

class LLMEngineerPayload(BaseModel):
    task_id: str
    task_type: str
    pipeline_type: str
    original_user_query: str
    task_query: Optional[str] = None
    source: SourceInfo
    retrieved_document_context: List[ChunkContext] = Field(default_factory=list)
    memory_context: Optional[MemoryContext] = None
    strict_grounding_policy: StrictGroundingPolicy
    expected_llm_output_format: ExpectedLLMOutputFormat


# Output Payloads Returned by LLM Engineer

class LLMUsageMetrics(BaseModel):
    provider: str
    model: str
    key_alias: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int

class LLMResponsePayload(BaseModel):
    task_id: str
    status: Literal["success", "failure"]
    output_text: Optional[str] = None
    output_json: Optional[Any] = None
    source_chunk_ids: List[str] = Field(default_factory=list)
    usage_metrics: Optional[LLMUsageMetrics] = None
    error_message: Optional[str] = None
