import asyncio
from typing import List, Dict, Any, Optional
from app.schemas.ai_schema import ExecutionPlan, Task, TaskResult, AIResponse, Citation
from app.ai_system.orchestrator.pipeline_registry import PIPELINE_REGISTRY
from app.ai_system.orchestrator.constants import (
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL,
    NO_ANSWER_FALLBACK
)
from app.ai_system.orchestrator.errors import AllTasksFailedError, ExecutionError

class TaskOrchestrator:
    """
    Orchestrator that executes the ExecutionPlan using single, parallel, or sequential modes,
    and merges the resulting TaskResults into a unified AIResponse.
    """

    async def execute(self, plan: ExecutionPlan, request: Any) -> AIResponse:
        """
        Executes the plan and merges the results.
        """
        if not plan.tasks:
            # Plan has no tasks (e.g., clarification required)
            status = "needs_clarification"
            if plan.needs_clarification:
                message = plan.clarification_question or "Clarification required."
            else:
                message = "No tasks planned."
            return AIResponse(
                status=status,
                message=message,
                execution_mode=plan.execution_mode,
                tasks=[],
                citations=[],
                confidence=1.0,
                metadata={"mock": True}
            )

        task_results: Dict[str, TaskResult] = {}

        if plan.execution_mode == MODE_SINGLE:
            # Single task execution
            task = plan.tasks[0]
            result = await self._execute_task(task, request)
            task_results[task.task_id] = result

        elif plan.execution_mode == MODE_PARALLEL:
            # Parallel independent tasks execution using asyncio.gather
            tasks_to_run = [self._execute_task(t, request) for t in plan.tasks]
            results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
            
            for task, res in zip(plan.tasks, results):
                if isinstance(res, Exception):
                    task_results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        type=task.type,
                        status="failed",
                        content="",
                        citations=[],
                        confidence=0.0,
                        error=str(res),
                        metadata={"mock": True}
                    )
                else:
                    task_results[task.task_id] = res

        elif plan.execution_mode == MODE_SEQUENTIAL:
            # Sequential task execution (respecting depends_on list order)
            # Since the planner schedules them topologically, we can execute them sequentially in order.
            for task in plan.tasks:
                # Check if dependencies failed
                dep_failed = False
                for dep_id in task.depends_on:
                    dep_res = task_results.get(dep_id)
                    if not dep_res or dep_res.status in ["failed", "no_answer"]:
                        dep_failed = True
                        break
                
                if dep_failed:
                    task_results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        type=task.type,
                        status="failed",
                        content="",
                        citations=[],
                        confidence=0.0,
                        error="Prerequisite task failed or returned no answer.",
                        metadata={"mock": True}
                    )
                else:
                    result = await self._execute_task(task, request, task_results)
                    task_results[task.task_id] = result
        else:
            raise ExecutionError(f"Unsupported execution mode: {plan.execution_mode}")

        return self._merge_results(task_results, plan.execution_mode)

    async def _execute_task(self, task: Task, request: Any, previous_results: Optional[Dict[str, TaskResult]] = None) -> TaskResult:
        """Executes a single task by routing it to its registered pipeline wrapper."""
        pipeline_fn = PIPELINE_REGISTRY.get(task.type)
        if not pipeline_fn:
            return TaskResult(
                task_id=task.task_id,
                type=task.type,
                status="failed",
                content="",
                citations=[],
                confidence=0.0,
                error=f"No pipeline registered for task type: '{task.type}'",
                metadata={"mock": True}
            )
        
        try:
            # Inject optional parameters (difficulty, number_of_questions, etc.) from task metadata to request
            if task.metadata:
                for k, v in task.metadata.items():
                    if not hasattr(request, k) or getattr(request, k) is None:
                        setattr(request, k, v)

            return await pipeline_fn(task, request, previous_results)
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                type=task.type,
                status="failed",
                content="",
                citations=[],
                confidence=0.0,
                error=str(e),
                metadata={"mock": True}
            )

    def _merge_results(self, task_results: Dict[str, TaskResult], mode: str) -> AIResponse:
        """Merges multiple TaskResult outputs into one consolidated AIResponse."""
        results_list = list(task_results.values())
        
        # 1. Check for "all no_answer"
        all_no_answer = all(r.status == "no_answer" for r in results_list)
        if all_no_answer:
            return AIResponse(
                status="no_answer",
                message=NO_ANSWER_FALLBACK,
                execution_mode=mode,
                tasks=results_list,
                citations=[],
                confidence=0.0,
                metadata={"mock": True}
            )

        # 2. Check for "all failed"
        all_failed = all(r.status == "failed" for r in results_list)
        if all_failed:
            # Unexpected internal errors raise AllTasksFailedError to return HTTP 500
            raise AllTasksFailedError("ALL_TASKS_FAILED")

        # 3. Consolidate statuses
        has_failed = any(r.status == "failed" for r in results_list)
        has_no_answer = any(r.status == "no_answer" for r in results_list)
        
        if has_failed or has_no_answer:
            response_status = "partial"
        else:
            response_status = "success"

        # 4. Merge content messages into formatted markdown
        message_parts = []
        for r in results_list:
            if r.status == "success":
                # Capitalize task header for clean markdown layout
                header = r.type.replace("_", " ").title()
                message_parts.append(f"### {header}\n{r.content}")
            elif r.status == "no_answer":
                header = r.type.replace("_", " ").title()
                message_parts.append(f"### {header}\n*{NO_ANSWER_FALLBACK}*")
            elif r.status == "failed":
                header = r.type.replace("_", " ").title()
                message_parts.append(f"### {header}\n*Error executing task: {r.error}*")

        merged_message = "\n\n".join(message_parts)

        # 5. Aggregate Citations and deduplicate by chunk_id
        citations_map: Dict[str, Citation] = {}
        for r in results_list:
            for cit in r.citations:
                if cit.chunk_id not in citations_map:
                    citations_map[cit.chunk_id] = cit
                else:
                    # Update score if existing has lower score
                    existing_score = citations_map[cit.chunk_id].score or 0.0
                    new_score = cit.score or 0.0
                    if new_score > existing_score:
                        citations_map[cit.chunk_id].score = new_score
        
        merged_citations = list(citations_map.values())

        # 6. Calculate average confidence across successful/no_answer tasks (non-failed)
        valid_confidences = [r.confidence for r in results_list if r.status != "failed"]
        avg_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0

        return AIResponse(
            status=response_status,
            message=merged_message,
            execution_mode=mode,
            tasks=results_list,
            citations=merged_citations,
            confidence=avg_confidence,
            metadata={"mock": True}
        )
