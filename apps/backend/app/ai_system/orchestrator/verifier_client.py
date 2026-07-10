from abc import ABC, abstractmethod
from typing import Optional, List, Any
import json
import logging
from pydantic import BaseModel
from app.schemas.ai_schema import VerificationPolicy

logger = logging.getLogger(__name__)

class VerificationResult(BaseModel):
    passed: bool
    final_answer: str
    grounding_score: float = 1.0
    relevance_score: float = 1.0
    format_valid: bool = True
    issues: List[str] = []
    action: str = "return"  # "return" | "fallback" | "retry"
    confidence: float = 1.0

    @property
    def success(self) -> bool:
        return self.passed

    @property
    def schema_valid(self) -> bool:
        return self.format_valid

    @property
    def reason(self) -> Optional[str]:
        return ", ".join(self.issues) if self.issues else None


class VerifierClient(ABC):
    """Abstract Base Class defining the verifier/grounding agent contract."""
    
    @abstractmethod
    async def verify(
        self,
        *,
        user_query: str,
        intent: str,
        retrieved_chunks: List[Any],
        llm_output: str,
        output_format: str,
        citations: List[Any],
        policy: VerificationPolicy
    ) -> VerificationResult:
        """
        Verifies LLM response grounding, schema compliance, relevance, and completeness.
        """
        pass


class RealVerifierClient(VerifierClient):
    """Production verifier that performs rule-based and LLM-assisted verification."""
    
    async def verify(
        self,
        *,
        user_query: str,
        intent: str,
        retrieved_chunks: List[Any],
        llm_output: str,
        output_format: str,
        citations: List[Any],
        policy: VerificationPolicy
    ) -> VerificationResult:
        import os
        from app.ai_system.services.llm.config import LLMConfig
        from app.ai_system.validation.verifier import verify_response
        from app.ai_system.validation.schemas import RetrievedChunk as ValRetrievedChunk, TaskType as ValTaskType
        
        # Decide if we can run LLM judge based on keys configuration
        use_llm_judge = True
        v_keys = LLMConfig.verifier_keys()
        if not v_keys or any("dummy" in k for k in v_keys):
            use_llm_judge = False
            
        # Map retrieved chunks to validation schemas
        val_chunks = []
        for c in retrieved_chunks:
            val_chunks.append(ValRetrievedChunk(
                chunk_id=str(c.get("id") if isinstance(c, dict) else getattr(c, "chunk_id", "")),
                text=str(c.get("content") if isinstance(c, dict) else getattr(c, "text", "")),
                page_number=c.get("page_start") if isinstance(c, dict) else getattr(c, "page_number", 1),
                section_title=c.get("section_title") if isinstance(c, dict) else getattr(c, "section_title", None),
                similarity_score=c.get("score") if isinstance(c, dict) else getattr(c, "similarity_score", None)
            ))
            
        # Map intent to validation TaskType
        intent_map = {
            "chat_answer": ValTaskType.CHAT,
            "explain": ValTaskType.EXPLAIN,
            "summary": ValTaskType.SUMMARY,
            "quiz": ValTaskType.QUIZ,
            "answer_evaluation": ValTaskType.ANSWER_EVALUATION
        }
        val_task_type = intent_map.get(intent, ValTaskType.CHAT)
        
        # Parse quiz data if quiz
        quiz_data = None
        if val_task_type == ValTaskType.QUIZ:
            try:
                cleaned = llm_output.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                quiz_data = json.loads(cleaned.strip())
            except Exception:
                pass
                
        # Invoke validation package verifier
        val_res = await verify_response(
            user_query=user_query,
            task_type=val_task_type,
            retrieved_chunks=val_chunks,
            executor_output=llm_output,
            quiz_data=quiz_data,
            use_llm_judge=use_llm_judge
        )
        
        # Map actions: retrieve_more is degraded to fallback as per architectural constraints
        action_map = {
            "return": "return",
            "regenerate": "retry",
            "retrieve_more": "fallback",
            "fallback": "fallback"
        }
        action_str = action_map.get(val_res.action.value, "return")
        
        format_valid = True
        if val_res.reasons:
            if any("format" in r.lower() or "json" in r.lower() or "quiz" in r.lower() for r in val_res.reasons):
                format_valid = False
                
        fallback_msg = "لم أجد إجابة واضحة في الملف المرفوع."
        final_ans = val_res.final_answer or llm_output
        if action_str == "fallback":
            final_ans = fallback_msg
            
        grounding_score = val_res.metadata.get("factors", {}).get("grounding_score", 1.0)
        relevance_score = val_res.metadata.get("factors", {}).get("context_relevance_score", 1.0)
        
        return VerificationResult(
            passed=val_res.passed,
            final_answer=final_ans,
            grounding_score=grounding_score,
            relevance_score=relevance_score,
            format_valid=format_valid,
            issues=val_res.reasons,
            action=action_str,
            confidence=val_res.confidence
        )

# Singleton production instance
default_verifier_client = RealVerifierClient()
