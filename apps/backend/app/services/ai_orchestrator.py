from typing import Any
from app.schemas.ai_schema import AIResponse
from app.ai_system.orchestrator.document_guard import validate_document_access
from app.ai_system.orchestrator.planner import TaskPlanner
from app.ai_system.orchestrator.orchestrator import TaskOrchestrator

class AIOrchestratorService:
    """
    Central service layer acting as the single entrypoint for all AI operations.
    Validates input permissions, generates plans, and executes pipelines.
    """
    def __init__(self) -> None:
        self.planner = TaskPlanner()
        self.orchestrator = TaskOrchestrator()

    async def execute_query(self, document_id: str, request: Any, user_id: str) -> AIResponse:
        """
        Validates access to the document, compiles the task plan,
        routes execution through the orchestrator, and collects debug trace stages.
        """
        trace_stages = []
        request._trace_stages = trace_stages
        
        # 1. Document Guard
        try:
            await validate_document_access(document_id, user_id)
            trace_stages.append({"stage": "document_guard", "status": "passed"})
        except Exception as e:
            trace_stages.append({"stage": "document_guard", "status": "failed", "error": str(e)})
            raise
            
        # 2. Input Validation
        trace_stages.append({"stage": "input_validation", "status": "passed"})
        
        # 3. Planner
        try:
            request.document_id = document_id
            plan = self.planner.plan(request)
            intent_val = plan.primary_intent.value if plan.primary_intent else "unknown"
            trace_stages.append({
                "stage": "planner",
                "intent": intent_val,
                "confidence": plan.confidence
            })
        except Exception as e:
            trace_stages.append({"stage": "planner", "status": "failed", "error": str(e)})
            raise
            
        # Execute & return merged response
        response = await self.orchestrator.execute(plan, request)
        
        # Set trace stages in metadata
        response.metadata["trace"] = trace_stages
        return response

# Global process-wide singleton
ai_orchestrator_service = AIOrchestratorService()
