import asyncio
import json
import pytest
from app.ai_system.streaming.stage_events import AIStageEvent, PublicAIStage, StageStatus
from app.ai_system.streaming.stage_emitter import set_current_emitter, clear_current_emitter, emit_stage_event, get_current_request_id
from app.ai_system.streaming.public_request_summary import build_public_request_summary
from app.schemas.ai_schema import DAGPlan, Task, TaskType, ExecutionMode

def test_event_serialization():
    # Verify AIStageEvent serializes properly
    event = AIStageEvent(
        request_id="req-123",
        node_id="task-1",
        stage=PublicAIStage.RETRIEVAL,
        status=StageStatus.STARTED,
        label_key="ai_stage.retrieval",
        message="Searching the document",
        progress=45.0,
        timestamp="2026-07-17T06:30:00Z",
        metadata={"candidate_count": 5}
    )
    serialized = event.model_dump_json()
    data = json.loads(serialized)
    assert data["request_id"] == "req-123"
    assert data["stage"] == "retrieval"
    assert data["status"] == "started"
    assert data["progress"] == 45.0

@pytest.mark.asyncio
async def test_emitter_request_isolation():
    events_1 = []
    events_2 = []

    async def cb1(event):
        events_1.append(event)

    async def cb2(event):
        events_2.append(event)

    async def run_client_1():
        set_current_emitter("req-1", cb1)
        await asyncio.sleep(0.01)
        await emit_stage_event(PublicAIStage.RETRIEVAL, StageStatus.STARTED, progress=10.0)
        assert get_current_request_id() == "req-1"
        clear_current_emitter()

    async def run_client_2():
        set_current_emitter("req-2", cb2)
        await emit_stage_event(PublicAIStage.GENERATION, StageStatus.STARTED, progress=20.0)
        assert get_current_request_id() == "req-2"
        clear_current_emitter()

    # Run concurrently
    await asyncio.gather(run_client_1(), run_client_2())

    assert len(events_1) == 1
    assert events_1[0].request_id == "req-1"
    assert events_1[0].stage == "retrieval"

    assert len(events_2) == 1
    assert events_2[0].request_id == "req-2"
    assert events_2[0].stage == "generation"

@pytest.mark.asyncio
async def test_metadata_sanitization():
    emitted_events = []
    async def cb(event):
        emitted_events.append(event)

    set_current_emitter("req-meta", cb)
    
    # Emit with some allowed and some forbidden metadata keys
    await emit_stage_event(
        PublicAIStage.RETRIEVAL,
        StageStatus.COMPLETED,
        progress=50.0,
        metadata={
            "candidate_count": 6,
            "secret_api_key": "hidden_value",
            "task_type": "explain"
        }
    )
    clear_current_emitter()

    assert len(emitted_events) == 1
    meta = emitted_events[0].metadata
    assert meta is not None
    assert meta["candidate_count"] == 6
    assert meta["task_type"] == "explain"
    assert "secret_api_key" not in meta

def test_public_request_summary_builder():
    class DummyRequest:
        def __init__(self, summary_style=None, summary_size=None, question_count=None, difficulty=None):
            self.summary_style = summary_style
            self.summary_size = summary_size
            self.question_count = question_count
            self.difficulty = difficulty

    # 1. Chat Answer
    task1 = Task(task_id="t1", type=TaskType.CHAT_ANSWER, query="what is photosynthesis?")
    plan1 = DAGPlan(plan_id="p1", primary_intent=TaskType.CHAT_ANSWER, execution_mode=ExecutionMode.SINGLE, tasks=[task1])
    summary1 = build_public_request_summary(plan1, DummyRequest())
    assert " photosynthesis" in summary1

    # 2. Summary Request
    task2 = Task(task_id="t2", type=TaskType.SUMMARY, query="summarize")
    plan2 = DAGPlan(plan_id="p2", primary_intent=TaskType.SUMMARY, execution_mode=ExecutionMode.SINGLE, tasks=[task2])
    summary2 = build_public_request_summary(plan2, DummyRequest(summary_style="bullet_points", summary_size="concise"))
    assert "concise bullet_points summary" in summary2

    # 3. Quiz Request
    task3 = Task(task_id="t3", type=TaskType.QUIZ, query="quiz")
    plan3 = DAGPlan(plan_id="p3", primary_intent=TaskType.QUIZ, execution_mode=ExecutionMode.SINGLE, tasks=[task3])
    summary3 = build_public_request_summary(plan3, DummyRequest(question_count=10, difficulty="hard"))
    assert "10 hard-level quiz questions" in summary3

    # 4. Compound Request
    plan4 = DAGPlan(plan_id="p4", primary_intent=TaskType.EXPLAIN, execution_mode=ExecutionMode.SEQUENTIAL, tasks=[
        Task(task_id="t4_1", type=TaskType.EXPLAIN, query="explain SVM"),
        Task(task_id="t4_2", type=TaskType.QUIZ, query="quiz", metadata={"question_count": 3})
    ])
    summary4 = build_public_request_summary(plan4, DummyRequest(difficulty="easy"))
    assert "explain" in summary4
    assert "quiz questions" in summary4
