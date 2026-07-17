from typing import Any
from app.schemas.ai_schema import AIResponse
from app.ai_system.orchestrator.document_guard import validate_document_access
from app.ai_system.orchestrator.planner import TaskPlanner
from app.ai_system.orchestrator.orchestrator import TaskOrchestrator
from app.ai_system.validation.input_validator import validate_input

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
        from app.ai_system.orchestrator.pipeline_state import PipelineState, PipelineRequestContext

        pipeline_state = PipelineState()
        context = PipelineRequestContext(request=request, state=pipeline_state)
        # Store on raw request too for backward compatibility with external code
        try:
            request._pipeline_state = pipeline_state
        except Exception:
            pass
        
        # Backward-compat: keep _trace_stages for code that references it directly
        request._trace_stages = pipeline_state.trace_stages
        trace_stages = pipeline_state.trace_stages
        
        # 1. Document Guard
        from app.ai_system.streaming.stage_emitter import emit_stage_event
        from app.ai_system.streaming.stage_events import PublicAIStage, StageStatus

        try:
            await emit_stage_event(PublicAIStage.DOCUMENT_CHECK, StageStatus.STARTED, progress=5.0)
            await validate_document_access(document_id, user_id)
            await emit_stage_event(PublicAIStage.DOCUMENT_CHECK, StageStatus.COMPLETED, progress=10.0)
            trace_stages.append({"stage": "document_guard", "status": "passed"})
        except Exception as e:
            await emit_stage_event(PublicAIStage.DOCUMENT_CHECK, StageStatus.FAILED, f"Document access denied: {e}", progress=10.0)
            trace_stages.append({"stage": "document_guard", "status": "failed", "error": str(e)})
            raise
            
        # 2. Input Validation
        query_text = getattr(request, "message", None)
        if query_text is None:
            if hasattr(request, "summary_style"):
                query_text = "Summarize the document"
            elif hasattr(request, "difficulty"):
                query_text = "Generate a quiz from the document"
            else:
                query_text = "Process document"

        from app.ai_system.validation.schemas import RequestType, ResponseStrategy, DocumentTaskType, TaskType as ValTaskType
        from app.ai_system.validation.dynamic_response import compose_dynamic_response
        from app.ai_system.validation.verifier import verify_response
        from app.schemas.ai_schema import ExecutionMode
        
        await emit_stage_event(PublicAIStage.INPUT_ANALYSIS, StageStatus.STARTED, progress=12.0)
        validation_result = await validate_input(
            raw_text=query_text,
            document_id=document_id,
            user_id=user_id
        )
        await emit_stage_event(PublicAIStage.INPUT_ANALYSIS, StageStatus.COMPLETED, progress=18.0)
        
        # Store validation result in pipeline state and raw request (for backward compat)
        pipeline_state.input_validation = validation_result
        request._input_validation = validation_result
        lang = validation_result.language
        
        # A. Intercept non-pipeline strategy (greetings, abuse-only, prompt injection)
        if not validation_result.allow_pipeline:
            composed_text = compose_dynamic_response(validation_result.response_strategy, lang=lang)
            
            # Deterministic output verifier check
            verification = await verify_response(
                user_query=query_text,
                task_type=ValTaskType.CHAT,
                retrieved_chunks=[],
                executor_output=composed_text,
                response_strategy=validation_result.response_strategy,
                primary_task=validation_result.primary_task
            )
            
            is_injection = validation_result.request_type == RequestType.prompt_injection
            is_abuse = validation_result.request_type == RequestType.abuse_only
            
            status_str = "prompt_injection" if is_injection else (
                "invalid_input" if is_abuse else (
                    "needs_clarification" if validation_result.response_strategy in [
                        ResponseStrategy.generate_greeting_response,
                        ResponseStrategy.generate_clarification
                    ] else "success"
                )
            )
            
            trace_stages.append({
                "stage": "input_validation",
                "status": "intercepted",
                "strategy": validation_result.response_strategy.value
            })
            
            # For early response paths: skip irrelevant stages and emit completed
            await emit_stage_event(
                stage=PublicAIStage.COMPLETED,
                status=StageStatus.COMPLETED,
                progress=100.0,
                content=verification.final_answer or composed_text,
                citations=[]
            )

            return AIResponse(
                status=status_str,
                message=verification.final_answer or composed_text,
                execution_mode=ExecutionMode.SINGLE,
                tasks=[],
                citations=[],
                confidence=1.0,
                metadata={
                    "trace": trace_stages,
                    "response_strategy": validation_result.response_strategy.value
                }
            )
            
        # B. Intercept document metadata query (uses verified database props, 0 LLM calls)
        if validation_result.primary_task == DocumentTaskType.document_metadata_query:
            from app.ai_system.validation.metadata_router import resolve_metadata_query
            metadata_answer = await resolve_metadata_query(document_id, query_text, lang=lang)
            
            verification = await verify_response(
                user_query=query_text,
                task_type=ValTaskType.CHAT,
                retrieved_chunks=[],
                executor_output=metadata_answer,
                response_strategy=validation_result.response_strategy,
                primary_task=validation_result.primary_task
            )
            
            trace_stages.append({
                "stage": "metadata_lookup",
                "status": "completed"
            })
            
            # Emit completed early for metadata route
            await emit_stage_event(
                stage=PublicAIStage.COMPLETED,
                status=StageStatus.COMPLETED,
                progress=100.0,
                content=verification.final_answer or metadata_answer,
                citations=[]
            )

            return AIResponse(
                status="success",
                message=verification.final_answer or metadata_answer,
                execution_mode=ExecutionMode.SINGLE,
                tasks=[],
                citations=[],
                confidence=1.0,
                metadata={
                    "trace": trace_stages,
                    "primary_task": "document_metadata_query"
                }
            )
            
        # C. Proceed normal pipeline
        trace_stages.append({
            "stage": "input_validation",
            "status": "passed",
            "sanitized": validation_result.sanitized_input
        })
        if hasattr(request, "message"):
            request.message = validation_result.sanitized_input
            context.message = validation_result.sanitized_input
        
        # 3. Planner
        try:
            request.document_id = document_id
            plan = await self.planner.plan(request)
            intent_val = plan.primary_intent.value if plan.primary_intent else "unknown"
            trace_stages.append({
                "stage": "planner",
                "intent": intent_val,
                "confidence": plan.confidence
            })
        except Exception as e:
            trace_stages.append({"stage": "planner", "status": "failed", "error": str(e)})
            raise
            
        response = await self.orchestrator.execute(plan, context)
        
        # 4. Final Output Validation
        if response.status in ["success", "partial"]:
            import json
            from app.ai_system.validation.output_validator import validate_output
            from app.ai_system.validation.schemas import TaskType as ValTaskType, HallucinationCheckResult, HallucinationAction, OutputAction, ResponseStrategy
            
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
            
            strategy_val = getattr(request, "_input_validation", None).response_strategy if getattr(request, "_input_validation", None) else ResponseStrategy.continue_to_planner
            primary_task_val = getattr(request, "_input_validation", None).primary_task if getattr(request, "_input_validation", None) else None

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
                    quiz_data=quiz_data,
                    response_strategy=strategy_val,
                    primary_task=primary_task_val,
                    query=query_text
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
                            quiz_data=quiz_data,
                            response_strategy=strategy_val,
                            primary_task=primary_task_val,
                            query=query_text
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
        
        # Copy quiz and personalization metadata from tasks to the response root if present
        for t in response.tasks:
            t_type = t.type.value if hasattr(t.type, "value") else str(t.type)
            if t_type == "quiz" and t.status == "success" and "quiz" in t.metadata:
                response.metadata["quiz"] = t.metadata["quiz"]
            if t.metadata and "personalization" in t.metadata:
                response.metadata["personalization"] = t.metadata["personalization"]

        # Set trace stages in metadata
        response.metadata["trace"] = trace_stages
        return response

# Global process-wide singleton
ai_orchestrator_service = AIOrchestratorService()
