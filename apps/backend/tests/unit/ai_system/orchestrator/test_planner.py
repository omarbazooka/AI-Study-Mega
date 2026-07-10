import pytest
from pydantic import ValidationError
from app.schemas.ai_schema import (
    PDFChatRequest,
    SummaryRequest,
    QuizRequest,
    TaskType,
    ExecutionMode,
    OutputFormat
)
from app.ai_system.orchestrator.planner import TaskPlanner
from app.ai_system.orchestrator.errors import PlanningError, CircularDependencyError

def test_request_schema_validation():
    # Valid Request
    req = PDFChatRequest(
        user_id="user_123",
        session_id="session_456",
        message="What is RAG?",
        language="en"
    )
    assert req.message == "What is RAG?"
    assert req.language == "en"

    # Invalid language
    with pytest.raises(ValidationError):
        PDFChatRequest(
            user_id="user_123",
            session_id="session_456",
            message="What is RAG?",
            language="fr"  # unsupported
        )

    # Empty message
    with pytest.raises(ValidationError):
        PDFChatRequest(
            user_id="user_123",
            session_id="session_456",
            message=""
        )


def test_summary_request_schema():
    # Valid Summary request
    req = SummaryRequest(
        user_id="user_123",
        session_id="session_456",
        language="ar",
        summary_style="bullet_points"
    )
    assert req.language == "ar"
    assert req.summary_style == "bullet_points"

    # Invalid language
    with pytest.raises(ValidationError):
        SummaryRequest(
            user_id="user_123",
            session_id="session_456",
            language="de"
        )


def test_quiz_request_schema():
    # Valid Quiz request
    req = QuizRequest(
        user_id="user_123",
        session_id="session_456",
        language="en",
        difficulty="hard",
        number_of_questions=10
    )
    assert req.difficulty == "hard"
    assert req.number_of_questions == 10

    # Invalid difficulty
    with pytest.raises(ValidationError):
        QuizRequest(
            user_id="user_123",
            session_id="session_456",
            difficulty="super_hard"
        )

    # Invalid number of questions
    with pytest.raises(ValidationError):
        QuizRequest(
            user_id="user_123",
            session_id="session_456",
            number_of_questions=0  # Only 1-20 allowed
        )


@pytest.mark.asyncio
async def test_planner_single_intent():
    planner = TaskPlanner()

    # Summary Arabic
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="لخصلي هاد الملف من فضلك", language="ar")
    plan = await planner.plan(req)
    assert plan.execution_mode == ExecutionMode.SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TaskType.SUMMARY
    assert not plan.needs_clarification

    # Quiz English
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="Make a quick quiz for me", language="en")
    plan = await planner.plan(req)
    assert plan.execution_mode == ExecutionMode.SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TaskType.QUIZ

    # Explain Arabic
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="ممكن تشرحلي القسم الأول؟", language="ar")
    plan = await planner.plan(req)
    assert plan.execution_mode == ExecutionMode.SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TaskType.EXPLAIN


@pytest.mark.asyncio
async def test_planner_compound_intents():
    planner = TaskPlanner()

    # Summary and Quiz (independent tasks -> parallel execution)
    req = PDFChatRequest(
        user_id="user_1",
        session_id="sess_1",
        message="Summarize this chapter and also generate a quiz for me",
        language="en"
    )
    plan = await planner.plan(req)
    assert plan.execution_mode == ExecutionMode.PARALLEL
    assert len(plan.tasks) == 2
    types = {t.type for t in plan.tasks}
    assert TaskType.SUMMARY in types
    assert TaskType.QUIZ in types
    for t in plan.tasks:
        assert len(t.depends_on) == 0

    # Quiz and Answer Table (dependent tasks -> hybrid/sequential execution batches)
    req = PDFChatRequest(
        user_id="user_1",
        session_id="sess_1",
        message="اعملي كويز على الملف واعمل جدول اجابات",
        language="ar"
    )
    plan = await planner.plan(req)
    assert plan.execution_mode == ExecutionMode.HYBRID
    assert len(plan.tasks) == 2
    
    quiz_task = next(t for t in plan.tasks if t.type == TaskType.QUIZ)
    ans_task = next(t for t in plan.tasks if t.type == TaskType.ANSWER_TABLE)
    
    assert ans_task.depends_on == [quiz_task.task_id]


@pytest.mark.asyncio
async def test_planner_vague_query_clarification():
    planner = TaskPlanner()

    # Vague query (non-greeting, short)
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="a", language="en")
    plan = await planner.plan(req)
    assert plan.needs_clarification
    assert "How can I help" in plan.clarification_question
    assert len(plan.tasks) == 0

    # Arabic short greeting is routed as conversational greeting
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="مرحبا", language="ar")
    plan = await planner.plan(req)
    assert not plan.needs_clarification
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TaskType.CHAT_ANSWER
    assert plan.tasks[0].metadata.get("is_greeting") is True


@pytest.mark.asyncio
async def test_planner_default_chat():
    planner = TaskPlanner()

    # Standard query with no intent keywords defaults to chat_answer
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="ما الذي يتحدث عنه القسم الثاني؟", language="ar")
    plan = await planner.plan(req)
    assert plan.execution_mode == ExecutionMode.SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TaskType.CHAT_ANSWER


def test_planner_circular_dependency_error():
    planner = TaskPlanner()
    from app.schemas.ai_schema import Task
    tasks = [
        Task(task_id="t1", type=TaskType.QUIZ, query="quiz", depends_on=["t2"]),
        Task(task_id="t2", type=TaskType.ANSWER_TABLE, query="answers", depends_on=["t1"])
    ]
    with pytest.raises(CircularDependencyError):
        planner._topological_sort(tasks)
