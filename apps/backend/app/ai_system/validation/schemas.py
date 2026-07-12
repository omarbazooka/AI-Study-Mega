from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class InputAction(str, Enum):
    CONTINUE = "continue"
    REJECT = "reject"
    ASK_CLARIFICATION = "ask_clarification"

# ------------------------------------------------------------------
# Section 7: Input Validation
# ------------------------------------------------------------------
class RequestType(str, Enum):
    greeting = "greeting"
    abuse_only = "abuse_only"
    prompt_injection = "prompt_injection"
    ambiguous_request = "ambiguous_request"
    document_task = "document_task"

class DocumentTaskType(str, Enum):
    document_factual_qa = "document_factual_qa"
    document_summary = "document_summary"
    document_explanation = "document_explanation"
    document_evaluation = "document_evaluation"
    document_critique = "document_critique"
    document_transformation = "document_transformation"
    document_rewrite = "document_rewrite"
    document_formatting = "document_formatting"
    document_gap_analysis = "document_gap_analysis"
    document_structure_analysis = "document_structure_analysis"
    document_metadata_query = "document_metadata_query"
    document_targeted_improvement = "document_targeted_improvement"
    document_comparison = "document_comparison"
    quiz_generation = "quiz_generation"
    unrelated_external_question = "unrelated_external_question"

class ExecutionStrategy(str, Enum):
    focused_retrieval = "focused_retrieval"
    section_coverage_retrieval = "section_coverage_retrieval"
    full_document_context = "full_document_context"
    map_reduce_analysis = "map_reduce_analysis"
    metadata_lookup = "metadata_lookup"
    transformation_pipeline = "transformation_pipeline"

class ResponseStrategy(str, Enum):
    continue_to_planner = "continue_to_planner"
    generate_greeting_response = "generate_greeting_response"
    generate_respectful_boundary = "generate_respectful_boundary"
    answer_with_soft_boundary = "answer_with_soft_boundary"
    generate_clarification = "generate_clarification"
    block_prompt_injection = "block_prompt_injection"
    block_scope_bypass = "block_scope_bypass"
    request_document_upload = "request_document_upload"
    request_document_ready = "request_document_ready"
    generate_out_of_scope_response = "generate_out_of_scope_response"
    generate_partial_evidence_response = "generate_partial_evidence_response"
    generate_conflicting_evidence_response = "generate_conflicting_evidence_response"
    continue_to_executor = "continue_to_executor"
    regenerate_output = "regenerate_output"
    return_verified_output = "return_verified_output"
    emergency_static_fallback = "emergency_static_fallback"

class EvidenceStatus(str, Enum):
    sufficient = "sufficient"
    partial = "partial"
    insufficient = "insufficient"
    conflicting = "conflicting"

class InputValidationResult(BaseModel):
    valid: bool
    sanitized_input: str
    language: str  # "ar" | "en"
    request_type: RequestType
    primary_task: Optional[DocumentTaskType] = None
    secondary_tasks: List[DocumentTaskType] = Field(default_factory=list)
    requires_direct_evidence: bool = False
    requires_document_wide_coverage: bool = False
    requires_document_metadata: bool = False
    allows_professional_rubric: bool = False
    allows_transformation: bool = False
    context_strategy: Optional[ExecutionStrategy] = None
    requires_document_context: bool = False
    allow_pipeline: bool
    safety: Dict[str, Any] = Field(default_factory=dict)
    response_strategy: ResponseStrategy
    confidence: float = 1.0
    reasons: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    severity: Severity = Severity.LOW
    action: InputAction = InputAction.CONTINUE


class TaskType(str, Enum):
    CHAT = "chat"
    EXPLAIN = "explain"
    SUMMARY = "summary"
    QUIZ = "quiz"
    ANSWER_EVALUATION = "answer_evaluation"

class OutputAction(str, Enum):
    PASS = "pass"
    REGENERATE = "regenerate"
    FALLBACK = "fallback"

# ------------------------------------------------------------------
# Section 8: Output Validation
# ------------------------------------------------------------------
class OutputValidationResult(BaseModel):
    valid: bool
    reasons: List[str] = Field(default_factory=list)
    format_errors: List[str] = Field(default_factory=list)
    safety_errors: List[str] = Field(default_factory=list)
    action: OutputAction = OutputAction.PASS


class HallucinationAction(str, Enum):
    PASS = "pass"
    REGENERATE = "regenerate"
    RETRIEVE_MORE = "retrieve_more"
    FALLBACK = "fallback"

# ------------------------------------------------------------------
# Section 9: Hallucination Checking
# ------------------------------------------------------------------
class HallucinationCheckResult(BaseModel):
    grounded: bool
    grounding_score: float = 0.0
    unsupported_claims: List[str] = Field(default_factory=list)
    supported_claims: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    suggested_action: HallucinationAction = HallucinationAction.PASS


# ------------------------------------------------------------------
# Section 10: Citation Building
# ------------------------------------------------------------------
class Citation(BaseModel):
    chunk_id: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    text_snippet: str
    relevance_score: Optional[float] = None

class CitationBuildResult(BaseModel):
    citations: List[Citation] = Field(default_factory=list)
    coverage_score: float = 0.0
    uncited_claims: List[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Retrieved Context
# ------------------------------------------------------------------
class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    similarity_score: Optional[float] = None


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ConfidenceAction(str, Enum):
    RETURN = "return"
    REGENERATE = "regenerate"
    RETRIEVE_MORE = "retrieve_more"
    FALLBACK = "fallback"

# ------------------------------------------------------------------
# Section 11: Confidence Scoring
# ------------------------------------------------------------------
class ConfidenceResult(BaseModel):
    score: float
    label: ConfidenceLabel
    factors: Dict[str, float] = Field(default_factory=dict)
    action: ConfidenceAction


# ------------------------------------------------------------------
# Section 12: Verification Orchestrator
# ------------------------------------------------------------------
class VerifierAction(str, Enum):
    RETURN = "return"
    REGENERATE = "regenerate"
    RETRIEVE_MORE = "retrieve_more"
    FALLBACK = "fallback"

class VerificationResult(BaseModel):
    passed: bool
    action: VerifierAction
    confidence: float
    reasons: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    final_answer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
