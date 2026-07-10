import asyncio
import json
from typing import List, Dict, Any, Optional
from app.schemas.ai_schema import ExecutionPlan, Task, TaskResult, AIResponse, Citation, ExecutionMode
from app.ai_system.orchestrator.pipeline_registry import PIPELINE_REGISTRY
from app.ai_system.orchestrator.constants import (
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL,
    MODE_HYBRID,
    NO_ANSWER_FALLBACK
)
from app.ai_system.orchestrator.errors import AllTasksFailedError, ExecutionError

class TaskOrchestrator:
    """
    Orchestrator that executes the ExecutionPlan using single, parallel, sequential,
    or hybrid dependency DAG execution, and merges the resulting TaskResults into a unified AIResponse.
    """

    async def execute(self, plan: ExecutionPlan, request: Any) -> AIResponse:
        """
        Executes the plan according to the specified execution mode and dependencies.
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

        completed_results: Dict[str, TaskResult] = {}
        pending_tasks = list(plan.tasks)

        # Batch-based topological loop scheduler (satisfies single, parallel, sequential, and hybrid DAGs)
        while pending_tasks:
            ready_tasks = []
            blocked_tasks = []
            
            for t in pending_tasks:
                deps_met = True
                dep_failed = False
                for dep_id in t.depends_on:
                    if dep_id not in completed_results:
                        deps_met = False
                    elif completed_results[dep_id].status in ["failed", "no_answer"]:
                        dep_failed = True
                
                if dep_failed:
                    # Prerequisite failed -> mark this task as failed immediately
                    completed_results[t.task_id] = TaskResult(
                        task_id=t.task_id,
                        type=t.type,
                        status="failed",
                        content="",
                        citations=[],
                        confidence=0.0,
                        error="Prerequisite task failed or returned no answer.",
                        metadata={"mock": False}
                    )
                    blocked_tasks.append(t)
                elif deps_met:
                    ready_tasks.append(t)
            
            # Remove blocked tasks from execution loop
            for t in blocked_tasks:
                pending_tasks.remove(t)
            
            if not ready_tasks:
                if pending_tasks:
                    # Cycle or unresolvable dependencies detected
                    for t in pending_tasks:
                        completed_results[t.task_id] = TaskResult(
                            task_id=t.task_id,
                            type=t.type,
                            status="failed",
                            content="",
                            citations=[],
                            confidence=0.0,
                            error="Circular dependency or deadlocked task graph.",
                            metadata={"mock": False}
                        )
                    break
                else:
                    break

            # Execute ready tasks in parallel
            run_futures = [self._execute_task(t, request, completed_results) for t in ready_tasks]
            results = await asyncio.gather(*run_futures, return_exceptions=True)
            
            for t, res in zip(ready_tasks, results):
                if isinstance(res, Exception):
                    completed_results[t.task_id] = TaskResult(
                        task_id=t.task_id,
                        type=t.type,
                        status="failed",
                        content="",
                        citations=[],
                        confidence=0.0,
                        error=str(res),
                        metadata={"mock": False}
                    )
                else:
                    completed_results[t.task_id] = res
                
                pending_tasks.remove(t)

        return self._merge_results(completed_results, plan)

    async def _execute_task(self, task: Task, request: Any, previous_results: Optional[Dict[str, TaskResult]] = None) -> TaskResult:
        """Executes a single task by routing it to its registered pipeline wrapper."""
        pipeline_fn = PIPELINE_REGISTRY.get(task.type.value)
        if not pipeline_fn:
            return TaskResult(
                task_id=task.task_id,
                type=task.type,
                status="failed",
                content="",
                citations=[],
                confidence=0.0,
                error=f"No pipeline registered for task type: '{task.type.value}'",
                metadata={"mock": False}
            )
        
        try:
            # Inject optional parameters from task metadata to request
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
        intents = [t.type.value for t in plan.tasks]
        planner_trace = {
            "status": "completed",
            "mode": "rule_based",
            "llm_used": False,
            "intent": ", ".join(intents) if intents else "unknown",
            "execution_mode": plan.execution_mode.value,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "type": t.type.value,
                    "query": t.query,
                    "depends_on": t.depends_on
                } for t in plan.tasks
            ],
            "confidence": plan.confidence
        }

        # 2. Orchestrator Trace
        orchestrator_trace = {
            "status": "completed",
            "selected_execution_mode": plan.execution_mode.value,
            "selected_pipeline_names": [t.type.value for t in plan.tasks],
            "dag_mode": "used" if plan.execution_mode == ExecutionMode.HYBRID else "not_used",
            "parallel_sequential_hybrid_status": plan.execution_mode.value,
            "launched_task_names": [t.type.value for t in plan.tasks],
            "retrieval_status": "not_run",
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
                retrieved_memory_count = mem_info.get("retrieved_memory_count", 0)
                personalization_applied = mem_info.get("has_personalization", False)
                break

        memory_trace = {
            "memory_layer_checked": True,
            "retrieved_count": retrieved_memory_count,
            "profile_level": profile_level,
            "personalization_applied": personalization_applied
        }

        # 4. Retrieval (RAG) Trace
        retrieval_status = "not_run"
        retrieval_confidence = 0.0
        retrieval_chunks_used = 0
        retrieval_latency_ms = 0
        verifier_run = False
        
        for tr in results_list:
            if tr.metadata and "retrieval_info" in tr.metadata:
                r_info = tr.metadata["retrieval_info"]
                retrieval_status = r_info.get("status", "not_run")
                retrieval_confidence = r_info.get("confidence", 0.0)
                retrieval_chunks_used = r_info.get("chunks_used", 0)
                retrieval_latency_ms = r_info.get("latency_ms", 0)
            
            if tr.metadata and "verification_info" in tr.metadata:
                verifier_run = True

        orchestrator_trace["retrieval_status"] = retrieval_status
        orchestrator_trace["verifier_status"] = "passed" if verifier_run else "not_run"

        retrieval_trace = {
            "status": retrieval_status,
            "confidence": retrieval_confidence,
            "chunks_used": retrieval_chunks_used,
            "latency_ms": retrieval_latency_ms
        }

        return {
            "planner": planner_trace,
            "orchestrator": orchestrator_trace,
            "memory": memory_trace,
            "retrieval": retrieval_trace
        }

    def _merge_results(self, task_results: Dict[str, TaskResult], plan: ExecutionPlan) -> AIResponse:
        """Merges multiple TaskResult outputs into one consolidated AIResponse."""
        results_list = list(task_results.values())
        trace = self._construct_pipeline_trace(plan, task_results)
        
        # 1. Check for "all no_answer"
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

        # 2. Check for "all failed"
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

        # Concat individual success responses
        success_contents = []
        citations_list = []
        for r in results_list:
            if r.status == "success":
                if isinstance(r.content, str):
                    success_contents.append(r.content)
                elif r.content is not None:
                    success_contents.append(json.dumps(r.content, ensure_ascii=False))
                
                if r.citations:
                    citations_list.extend(r.citations)

        # Deduplicate citations if needed
        seen_chunks = set()
        deduped_citations = []
        for c in citations_list:
            if c.chunk_id not in seen_chunks:
                seen_chunks.add(c.chunk_id)
                deduped_citations.append(c)

        if success_contents:
            merged_message = "\n\n".join(success_contents)
        else:
            merged_message = NO_ANSWER_FALLBACK

        # Calculate dynamic merged confidence score from successful tasks
        if successful_tasks:
            merged_confidence = sum(t.confidence for t in successful_tasks) / len(successful_tasks)
        else:
            merged_confidence = 0.9

        return AIResponse(
            status=response_status,
            message=message,
            execution_mode=plan.execution_mode,
            tasks=results_list,
            citations=deduped_citations,
            confidence=merged_confidence,
            metadata={"mock": False},
            pipeline_trace=trace
        )
