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
                        metadata={"mock": False}
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
                        metadata={"mock": False}
                    )
                else:
                    result = await self._execute_task(task, request, task_results)
                    task_results[task.task_id] = result
        else:
            raise ExecutionError(f"Unsupported execution mode: {plan.execution_mode}")

        return self._merge_results(task_results, plan)

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
                metadata={"mock": False}
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
                metadata={"mock": False}
            )

    def _construct_pipeline_trace(self, plan: ExecutionPlan, task_results: Dict[str, TaskResult]) -> Dict[str, Any]:
        results_list = list(task_results.values())
        
        # 1. Planner Trace
        intents = [t.type for t in plan.tasks]
        planner_trace = {
            "status": "completed",
            "mode": "rule_based",
            "llm_used": False,
            "intent": ", ".join(intents) if intents else "unknown",
            "execution_mode": plan.execution_mode,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "type": t.type,
                    "query": t.query,
                    "depends_on": t.depends_on
                } for t in plan.tasks
            ],
            "confidence": 0.0  # Do not show fake confidence values
        }

        # 2. Orchestrator Trace
        orchestrator_trace = {
            "status": "routed_only",
            "selected_execution_mode": plan.execution_mode,
            "selected_pipeline_names": [t.type for t in plan.tasks],
            "dag_mode": "not_used",
            "parallel_sequential_hybrid_status": "sequential" if plan.execution_mode == "single" else plan.execution_mode,
            "launched_task_names": [t.type for t in plan.tasks],
            "retrieval_status": "temporary_chunk_context_until_rag",
            "verifier_status": "not_run",
            "fallback_used": False
        }

        # 3. Memory Trace
        profile_level = "beginner"
        retrieved_memory_count = 0
        personalization_applied = False

        # Find first task result that has memory_info
        for tr in results_list:
            if tr.metadata and "memory_info" in tr.metadata:
                mem_info = tr.metadata["memory_info"]
                profile_level = mem_info.get("academic_level", "beginner")
                # Retrieve retrieved_memory_count safely
                retrieved_memory_count = mem_info.get("retrieved_memory_count", 0)
                personalization_applied = mem_info.get("has_personalization", False)
                break

        memory_trace = {
            "memory_layer_checked": True,
            "retrieved_count": retrieved_memory_count,
            "profile_level": profile_level,
            "personalization_applied": personalization_applied
        }

        return {
            "planner": planner_trace,
            "orchestrator": orchestrator_trace,
            "memory": memory_trace
        }

    def _merge_results(self, task_results: Dict[str, TaskResult], plan: ExecutionPlan) -> AIResponse:
        """Merges multiple TaskResult outputs into one consolidated AIResponse."""
        results_list = list(task_results.values())
        trace = self._construct_pipeline_trace(plan, task_results)
        
        # 1. Check for "all failed"
        all_failed = all(r.status == "failed" for r in results_list)
        if all_failed:
            raise AllTasksFailedError("ALL_TASKS_FAILED")

        # 2. Check for "all no_answer"
        all_no_answer = all(r.status == "no_answer" for r in results_list)
        if all_no_answer:
            return AIResponse(
                status="no_answer",
                message=NO_ANSWER_FALLBACK,
                execution_mode=plan.execution_mode,
                tasks=results_list,
                citations=[],
                confidence=0.0,
                metadata={"mock": False},
                pipeline_trace=trace
            )

        # 3. Consolidate statuses and content of successful tasks
        successful_tasks = [r for r in results_list if r.status == "success"]

        if not successful_tasks:
            # If no tasks succeeded, but some returned no_answer and some failed
            return AIResponse(
                status="no_answer",
                message=NO_ANSWER_FALLBACK,
                execution_mode=plan.execution_mode,
                tasks=results_list,
                citations=[],
                confidence=0.0,
                metadata={"mock": False},
                pipeline_trace=trace
            )

        if len(successful_tasks) == 1:
            message = successful_tasks[0].content
        else:
            # Multiple successful tasks: join their content with clear section headers
            parts = []
            for t in successful_tasks:
                header = t.type.replace("_", " ").title()
                parts.append(f"### {header}\n{t.content}")
            message = "\n\n".join(parts)

        # Collect citations across all task results without duplicates
        citations_map = {}
        for r in results_list:
            if r.citations:
                for c in r.citations:
                    if c.chunk_id not in citations_map:
                        citations_map[c.chunk_id] = c
                    else:
                        if c.score > citations_map[c.chunk_id].score:
                            citations_map[c.chunk_id] = c
        citations = list(citations_map.values())

        # Consolidate statuses
        has_failed = any(r.status == "failed" for r in results_list)
        has_no_answer = any(r.status == "no_answer" for r in results_list)
        
        if has_failed or has_no_answer:
            response_status = "partial"
        else:
            response_status = "success"

        return AIResponse(
            status=response_status,
            message=message,
            execution_mode=plan.execution_mode,
            tasks=results_list,
            citations=citations,
            confidence=0.9,
            metadata={"mock": False},
            pipeline_trace=trace
        )
