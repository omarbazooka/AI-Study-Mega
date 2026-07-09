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
class InputValidationResult(BaseModel):
    valid: bool
    sanitized_input: str
    reasons: List[str] = Field(default_factory=list)
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
