from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class PublicAIStage(str, Enum):
    REQUEST_RECEIVED = "request_received"
    DOCUMENT_CHECK = "document_check"
    INPUT_ANALYSIS = "input_analysis"
    PLANNING = "planning"
    PERSONALIZATION = "personalization"
    QUERY_PREPARATION = "query_preparation"
    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    CONTEXT_BUILDING = "context_building"
    GENERATION = "generation"
    QUIZ_GENERATION = "quiz_generation"
    VERIFICATION = "verification"
    CITATIONS = "citations"
    REFINING = "refining"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StageStatus(str, Enum):
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AIStageEvent(BaseModel):
    request_id: str
    node_id: Optional[str] = None
    stage: PublicAIStage
    status: StageStatus
    label_key: Optional[str] = None
    message: Optional[str] = None
    progress: float
    timestamp: str
    content: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
