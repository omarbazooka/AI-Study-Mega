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
        if hasattr(request, "message") and request.message:
            from app.ai_system.validation.input_validator import validate_input
            from app.ai_system.validation.schemas import InputAction
            from app.schemas.ai_schema import ExecutionMode
            
            validation_result = await validate_input(
                raw_text=request.message,
                document_id=document_id,
                user_id=user_id
            )
            
            if not validation_result.valid:
                is_injection = any("prompt injection" in r.lower() for r in validation_result.reasons)
                status_str = "prompt_injection" if is_injection else "invalid_input"
                
                trace_stages.append({
                    "stage": "input_validation",
                    "status": "failed",
                    "reasons": validation_result.reasons,
                    "severity": validation_result.severity.value,
                    "type": status_str
                })
                
                if validation_result.action == InputAction.REJECT:
                    from app.ai_system.validation.rules import FALLBACK_MESSAGE
                    return AIResponse(
                        status=status_str,
                        message=FALLBACK_MESSAGE,
                        execution_mode=ExecutionMode.SINGLE,
                        tasks=[],
                        citations=[],
                        confidence=0.0,
                        metadata={
                            "error": ", ".join(validation_result.reasons),
                            "trace": trace_stages,
                            "validation_type": status_str
                        }
                    )
            else:
                trace_stages.append({
                    "stage": "input_validation",
                    "status": "passed",
                    "sanitized": validation_result.sanitized_input
                })
                request.message = validation_result.sanitized_input
        else:
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
            
        response = await self.orchestrator.execute(plan, request)
        
        # 4. Final Output Validation
        if response.status in ["success", "partial"]:
            import json
            from app.ai_system.validation.output_validator import validate_output
            from app.ai_system.validation.schemas import TaskType as ValTaskType, HallucinationCheckResult, HallucinationAction, OutputAction
            
            intent_map = {
                "chat_answer": ValTaskType.CHAT,
                "explain": ValTaskType.EXPLAIN,
                "summary": ValTaskType.SUMMARY,
                "quiz": ValTaskType.QUIZ,
                "answer_evaluation": ValTaskType.ANSWER_EVALUATION
            }
            
            mock_hallucination = HallucinationCheckResult(
                grounded=True,
                grounding_score=1.0,
                suggested_action=HallucinationAction.PASS
            )
            
            all_valid = True
            first_fail_res = None
            
            tasks_to_validate = response.tasks if response.tasks else []
            if not tasks_to_validate:
                primary_intent = plan.primary_intent.value if plan.primary_intent else "chat_answer"
                val_task_type = intent_map.get(primary_intent, ValTaskType.CHAT)
                output_text = response.message
                quiz_data = None
                if val_task_type == ValTaskType.QUIZ and isinstance(output_text, str):
                    try:
                        import re
                        cleaned = output_text.strip()
                        cleaned = re.sub(r"\s*\[Personalized:[^\]]*\]", "", cleaned).strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        quiz_data = json.loads(cleaned.strip())
                    except Exception:
                        pass
                out_val_res = validate_output(
                    task_type=val_task_type,
                    output_text=str(output_text),
                    hallucination_result=mock_hallucination,
                    quiz_data=quiz_data
                )
                if not out_val_res.valid:
                    all_valid = False
                    first_fail_res = out_val_res
            else:
                for t in tasks_to_validate:
                    if t.status == "success":
                        t_type_str = t.type.value if hasattr(t.type, "value") else str(t.type)
                        val_task_type = intent_map.get(t_type_str, ValTaskType.CHAT)
                        output_text = t.content
                        quiz_data = None
                        if val_task_type == ValTaskType.QUIZ and isinstance(output_text, str):
                            try:
                                import re
                                cleaned = output_text.strip()
                                cleaned = re.sub(r"\s*\[Personalized:[^\]]*\]", "", cleaned).strip()
                                if cleaned.startswith("```json"):
                                    cleaned = cleaned[7:]
                                if cleaned.endswith("```"):
                                    cleaned = cleaned[:-3]
                                quiz_data = json.loads(cleaned.strip())
                            except Exception:
                                pass
                        
                        out_val_res = validate_output(
                            task_type=val_task_type,
                            output_text=str(output_text),
                            hallucination_result=mock_hallucination,
                            quiz_data=quiz_data
                        )
                        if not out_val_res.valid:
                            all_valid = False
                            first_fail_res = out_val_res
                            break
            
            trace_stages.append({
                "stage": "output_validation",
                "status": "passed" if all_valid else "failed",
                "reasons": (first_fail_res.reasons + first_fail_res.format_errors + first_fail_res.safety_errors) if first_fail_res else []
            })
            
            if not all_valid and first_fail_res:
                if first_fail_res.action in [OutputAction.FALLBACK, OutputAction.REGENERATE]:
                    from app.ai_system.validation.rules import FALLBACK_MESSAGE
                    response.message = FALLBACK_MESSAGE
                    response.status = "no_answer"
                    response.citations = []
                    response.confidence = 0.0
                    response.metadata["validation_error"] = ", ".join(first_fail_res.reasons + first_fail_res.format_errors)
        
        # Set trace stages in metadata
        response.metadata["trace"] = trace_stages
        return response

# Global process-wide singleton
ai_orchestrator_service = AIOrchestratorService()
