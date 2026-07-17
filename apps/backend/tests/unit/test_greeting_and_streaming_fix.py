"""
Targeted tests for the greeting early-return bug fix.

Covers:
  1. "اهلا بيك" returns greeting path (allow_pipeline=False) — no planner/retrieval/LLM/verifier.
  2. English "hello" also returns allow_pipeline=False.
  3. Valid PDF question (mocked LLM classifier) returns allow_pipeline=True.
  4. Unsupported question with empty retrieval returns safe fallback.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# 1. InputValidator: Arabic greeting with particle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_greeting_arabic_with_particle_returns_allow_pipeline_false():
    from app.ai_system.validation.input_validator import validate_input
    from app.ai_system.validation.schemas import RequestType

    with patch("app.ai_system.validation.input_validator._check_document_ready", new_callable=AsyncMock, return_value=True), \
         patch("app.ai_system.validation.input_validator._check_document_permissions", new_callable=AsyncMock, return_value=True):
        result = await validate_input(
            raw_text="اهلا بيك",
            document_id="doc-test-123",
            user_id="user-test-456"
        )

    assert result.request_type == RequestType.greeting, f"Expected greeting, got {result.request_type}"
    assert result.allow_pipeline is False, "Greeting must set allow_pipeline=False"
    assert result.valid is True, "Greeting is valid input but must not enter pipeline"


# ---------------------------------------------------------------------------
# 2. InputValidator: English greeting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_greeting_hello_english_returns_allow_pipeline_false():
    from app.ai_system.validation.input_validator import validate_input
    from app.ai_system.validation.schemas import RequestType

    with patch("app.ai_system.validation.input_validator._check_document_ready", new_callable=AsyncMock, return_value=True), \
         patch("app.ai_system.validation.input_validator._check_document_permissions", new_callable=AsyncMock, return_value=True):
        result = await validate_input(
            raw_text="hello",
            document_id="doc-test-123",
            user_id="user-test-456"
        )

    assert result.request_type == RequestType.greeting
    assert result.allow_pipeline is False


# ---------------------------------------------------------------------------
# 3. Valid PDF question returns allow_pipeline=True
#    (patching the LLM provider used at the bottom of validate_input)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_pdf_question_with_mocked_classifier_returns_allow_pipeline_true():
    from app.ai_system.validation.input_validator import validate_input
    from app.ai_system.validation.schemas import RequestType

    llm_json = json.dumps({
        "request_type": "document_task",
        "primary_task": "document_factual_qa",
        "secondary_tasks": [],
        "requires_direct_evidence": True,
        "requires_document_wide_coverage": False,
        "requires_document_metadata": False,
        "allows_professional_rubric": False,
        "allows_transformation": False,
        "context_strategy": "focused_retrieval",
        "contains_abuse": False,
        "abuse_severity": "none",
        "response_strategy": "continue_to_planner",
        "reasons": []
    })

    mock_prov_instance = MagicMock()
    mock_prov_instance.generate = AsyncMock(return_value={"text": llm_json})

    with patch("app.ai_system.validation.input_validator._check_document_ready", new_callable=AsyncMock, return_value=True), \
         patch("app.ai_system.validation.input_validator._check_document_permissions", new_callable=AsyncMock, return_value=True), \
         patch("app.ai_system.services.llm.model_router.resolve_config_for_role", return_value=("dummy-key", "llama-3.1-8b-instant")), \
         patch("app.ai_system.services.llm.providers.groq_provider.GroqProvider", return_value=mock_prov_instance), \
         patch("app.db.repositories.document_repository.get_by_id", new_callable=AsyncMock, return_value={"original_filename": "test.pdf"}):

        result = await validate_input(
            raw_text="ما هي أهداف الوثيقة؟",
            document_id="doc-test-123",
            user_id="user-test-456"
        )

    assert result.allow_pipeline is True, f"Expected allow_pipeline=True for real PDF question, got {result.allow_pipeline}"
    assert result.request_type == RequestType.document_task
    assert result.valid is True


# ---------------------------------------------------------------------------
# 4. Unsupported question with empty retrieval returns safe fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_out_of_scope_question_returns_fallback():
    from app.ai_system.orchestrator.pipeline_registry import execute_common_pipeline_steps
    from app.ai_system.validation.evidence_gate import EvidenceValidationResult
    from app.schemas.ai_schema import Task, TaskType, OutputFormat

    mock_evidence = EvidenceValidationResult(
        status="insufficient",
        reason_code="NO_CHUNKS_FOUND",
        usable_chunk_count=0,
        retrieved_count=0,
        document_match=True,
        recovery_recommended=False,
        threshold_profile="default",
        signals={}
    )

    mock_task = Task(
        task_id="task-001",
        type=TaskType.CHAT_ANSWER,
        query="ما هو عاصمة اليابان؟",
        retrieval_required=True,
        output_format=OutputFormat.MARKDOWN,
        metadata={}
    )

    mock_request = MagicMock()
    mock_request.user_id = "user-test"
    mock_request.session_id = "sess-test"
    mock_request.document_id = "doc-test-123"
    mock_request.language = "ar"
    mock_request._input_validation = None
    mock_request.state = None
    mock_request._pipeline_state = None
    mock_request._retrieval_result = None
    mock_request._trace_stages = []
    mock_request.verification_policy = None

    with patch("app.ai_system.validation.context_collector.collect_context", new_callable=AsyncMock, return_value=[]), \
         patch("app.ai_system.validation.evidence_gate.validate_evidence", new_callable=AsyncMock, return_value=mock_evidence), \
         patch("app.ai_system.orchestrator.pipeline_registry.store") as mock_store, \
         patch("app.ai_system.orchestrator.pipeline_registry.memory_retriever") as mock_memory:

        mock_store.save_message = AsyncMock(return_value=None)
        mock_memory.get_memory_context = AsyncMock(return_value=MagicMock(recent_messages=[]))

        result = await execute_common_pipeline_steps(
            task=mock_task,
            request=mock_request,
            task_type=TaskType.CHAT_ANSWER,
        )

    assert result.status == "no_answer", f"Expected no_answer, got {result.status}"
    assert result.content, "Fallback content must not be empty"
    assert result.citations == [], "Fallback must return no citations"

