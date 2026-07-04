import pytest
from pydantic import ValidationError
from app.schemas.ai_schema import PDFChatRequest, QuizRequest, SummaryRequest
from app.ai_system.orchestrator.planner import TaskPlanner
from app.ai_system.orchestrator.constants import (
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    TASK_EXPLAIN,
    TASK_CHAT_ANSWER,
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL
)
from app.ai_system.orchestrator.errors import PlanningError

def test_pydantic_schema_validations():
    # 1. Invalid language
    with pytest.raises(ValidationError):
        PDFChatRequest(
            user_id="user_123",
            session_id="session_456",
            message="hello",
            language="fr"  # Only 'ar' or 'en' allowed
        )

    # 2. Empty message
    with pytest.raises(ValidationError):
        PDFChatRequest(
            user_id="user_123",
            session_id="session_456",
            message=""
        )

    # 3. Message too long (> 1000 characters)
    with pytest.raises(ValidationError):
        PDFChatRequest(
            user_id="user_123",
            session_id="session_456",
            message="a" * 1001
        )

    # 4. Invalid quiz difficulty
    with pytest.raises(ValidationError):
        QuizRequest(
            user_id="user_123",
            session_id="session_456",
            difficulty="super_hard"  # Only 'easy', 'medium', 'hard' allowed
        )

    # 5. Invalid quiz question count
    with pytest.raises(ValidationError):
        QuizRequest(
            user_id="user_123",
            session_id="session_456",
            number_of_questions=25  # Only 1-20 allowed
        )

    with pytest.raises(ValidationError):
        QuizRequest(
            user_id="user_123",
            session_id="session_456",
            number_of_questions=0  # Only 1-20 allowed
        )


def test_planner_single_intent():
    planner = TaskPlanner()

    # Summary Arabic
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="لخصلي هاد الملف من فضلك", language="ar")
    plan = planner.plan(req)
    assert plan.execution_mode == MODE_SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TASK_SUMMARY
    assert not plan.needs_clarification

    # Quiz English
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="Make a quick quiz for me", language="en")
    plan = planner.plan(req)
    assert plan.execution_mode == MODE_SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TASK_QUIZ

    # Explain Arabic
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="ممكن تشرحلي القسم الأول؟", language="ar")
    plan = planner.plan(req)
    assert plan.execution_mode == MODE_SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TASK_EXPLAIN


def test_planner_compound_intents():
    planner = TaskPlanner()

    # Summary and Quiz (independent tasks -> parallel execution)
    req = PDFChatRequest(
        user_id="user_1",
        session_id="sess_1",
        message="Summarize this chapter and also generate a quiz for me",
        language="en"
    )
    plan = planner.plan(req)
    assert plan.execution_mode == MODE_PARALLEL
    assert len(plan.tasks) == 2
    types = {t.type for t in plan.tasks}
    assert TASK_SUMMARY in types
    assert TASK_QUIZ in types
    # No dependencies planned since they are independent
    for t in plan.tasks:
        assert len(t.depends_on) == 0

    # Quiz and Answer Table (dependent tasks -> sequential execution)
    req = PDFChatRequest(
        user_id="user_1",
        session_id="sess_1",
        message="اعملي كويز على الملف واعمل جدول اجابات",
        language="ar"
    )
    plan = planner.plan(req)
    assert plan.execution_mode == MODE_SEQUENTIAL
    assert len(plan.tasks) == 2
    
    quiz_task = next(t for t in plan.tasks if t.type == TASK_QUIZ)
    ans_task = next(t for t in plan.tasks if t.type == TASK_ANSWER_TABLE)
    
    assert ans_task.depends_on == [quiz_task.task_id]


def test_planner_vague_query_clarification():
    planner = TaskPlanner()

    # Short query
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="hi", language="en")
    plan = planner.plan(req)
    assert plan.needs_clarification
    assert "How can I help" in plan.clarification_question
    assert len(plan.tasks) == 0

    # Arabic short greeting
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="مرحبا", language="ar")
    plan = planner.plan(req)
    assert plan.needs_clarification
    assert "كيف يمكنني مساعدتك" in plan.clarification_question
    assert len(plan.tasks) == 0


def test_planner_default_chat():
    planner = TaskPlanner()

    # Standard query with no intent keywords defaults to chat_answer
    req = PDFChatRequest(user_id="user_1", session_id="sess_1", message="ما الذي يتحدث عنه القسم الثاني؟", language="ar")
    plan = planner.plan(req)
    assert plan.execution_mode == MODE_SINGLE
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type == TASK_CHAT_ANSWER
