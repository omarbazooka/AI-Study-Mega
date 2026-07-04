import pytest
from app.schemas.ai_schema import ExecutionPlan, Task, PDFChatRequest, TaskResult
from app.ai_system.orchestrator.orchestrator import TaskOrchestrator
from app.ai_system.orchestrator.constants import (
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL,
    NO_ANSWER_FALLBACK
)
from app.ai_system.orchestrator.errors import AllTasksFailedError

@pytest.mark.asyncio
async def test_orchestrator_single_success():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_SINGLE,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="Please summarize")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", message="Please summarize", language="en")
    
    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert response.execution_mode == MODE_SINGLE
    assert len(response.tasks) == 1
    assert response.tasks[0].type == TASK_SUMMARY
    assert response.tasks[0].status == "success"
    assert response.tasks[0].metadata["mock"] is True
    assert response.tasks[0].confidence == 0.5  # mock confidence
    assert "Document Comprehensive Summary" in response.message
    assert len(response.citations) > 0


@pytest.mark.asyncio
async def test_orchestrator_parallel_success():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_PARALLEL,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="summarize"),
            Task(task_id="t2", type=TASK_QUIZ, query="quiz")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", message="summarize and quiz", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert len(response.tasks) == 2
    types = {t.type for t in response.tasks}
    assert TASK_SUMMARY in types
    assert TASK_QUIZ in types
    assert "Document Comprehensive Summary" in response.message
    assert "Simulated Quiz" in response.message


@pytest.mark.asyncio
async def test_orchestrator_sequential_with_dependency():
    orchestrator = TaskOrchestrator()
    plan = ExecutionPlan(
        execution_mode=MODE_SEQUENTIAL,
        tasks=[
            Task(task_id="t1", type=TASK_QUIZ, query="quiz"),
            Task(task_id="t2", type=TASK_ANSWER_TABLE, query="answers", depends_on=["t1"])
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", message="quiz and answers", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "success"
    assert len(response.tasks) == 2
    
    ans_task = next(t for t in response.tasks if t.type == TASK_ANSWER_TABLE)
    assert ans_task.status == "success"
    assert ans_task.metadata["consumed_quiz_questions"] is True
    assert "What is the capital of Egypt?" in ans_task.content


@pytest.mark.asyncio
async def test_orchestrator_all_no_answer():
    orchestrator = TaskOrchestrator()
    # Trigger no answer using "outside the file" keyword in query
    plan = ExecutionPlan(
        execution_mode=MODE_SINGLE,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="outside the file")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", message="outside the file", language="ar")

    response = await orchestrator.execute(plan, req)
    assert response.status == "no_answer"
    assert response.message == NO_ANSWER_FALLBACK
    assert response.confidence == 0.0
    assert len(response.citations) == 0


@pytest.mark.asyncio
async def test_orchestrator_all_failed_raises_exception():
    orchestrator = TaskOrchestrator()
    # Use unregistered task type to force failure
    plan = ExecutionPlan(
        execution_mode=MODE_SINGLE,
        tasks=[
            Task(task_id="t1", type="nonexistent_type", query="test")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", message="test", language="en")

    with pytest.raises(AllTasksFailedError):
        await orchestrator.execute(plan, req)


@pytest.mark.asyncio
async def test_orchestrator_partial_failure():
    orchestrator = TaskOrchestrator()
    # One succeeds, one fails (unregistered type)
    plan = ExecutionPlan(
        execution_mode=MODE_PARALLEL,
        tasks=[
            Task(task_id="t1", type=TASK_SUMMARY, query="summarize"),
            Task(task_id="t2", type="broken_pipeline", query="broken")
        ]
    )
    req = PDFChatRequest(user_id="u1", session_id="s1", message="summarize and broken", language="en")

    response = await orchestrator.execute(plan, req)
    assert response.status == "partial"
    assert "Document Comprehensive Summary" in response.message
    assert "Error executing task" in response.message
    # Confidence is average of valid non-failed tasks (t1 confidence is 0.5, t2 failed so it's ignored or 0.5)
    assert response.confidence == 0.5
