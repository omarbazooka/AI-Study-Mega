import pytest
from unittest.mock import AsyncMock, MagicMock
from app.ai_system.services.llm.generation_service import GenerationService
from app.ai_system.services.llm.schemas import (
    LLMEngineerPayload,
    SourceInfo,
    StrictGroundingPolicy,
    ExpectedLLMOutputFormat,
    ChunkContext,
    MemoryContext
)
from app.ai_system.services.llm.api_key_pool import api_key_pool, APIKey

@pytest.mark.asyncio
async def test_generation_service_empty_context_fallback():
    payload = LLMEngineerPayload(
        task_id="task_1",
        task_type="chat_simple",
        pipeline_type="standard_rag",
        original_user_query="What is reinforcement learning?",
        source=SourceInfo(source_id="doc_1", source_type="document"),
        retrieved_document_context=[], # Empty context
        strict_grounding_policy=StrictGroundingPolicy(
            academic_source_of_truth="retrieved_document_context_only",
            memory_usage="personalization_only",
            if_document_context_insufficient="لم أجد إجابة واضحة في الملف المرفوع."
        ),
        expected_llm_output_format=ExpectedLLMOutputFormat(
            type="text",
            must_be_grounded=True,
            must_not_use_general_knowledge=True
        )
    )

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock()
    
    service = GenerationService(provider=mock_provider)
    response = await service.execute_task(payload)

    # Asserts
    assert response.status == "success"
    assert response.output_text == "لم أجد إجابة واضحة في الملف المرفوع."
    assert len(response.source_chunk_ids) == 0
    mock_provider.generate.assert_not_called()

@pytest.mark.asyncio
async def test_generation_service_successful_chat():
    payload = LLMEngineerPayload(
        task_id="task_2",
        task_type="chat_simple",
        pipeline_type="standard_rag",
        original_user_query="What is supervised learning?",
        source=SourceInfo(source_id="doc_1", source_type="document"),
        retrieved_document_context=[
            ChunkContext(chunk_id="chunk_a", page_number=1, content="Supervised learning uses labeled inputs.")
        ],
        strict_grounding_policy=StrictGroundingPolicy(
            academic_source_of_truth="retrieved_document_context_only",
            memory_usage="personalization_only",
            if_document_context_insufficient="لم أجد إجابة واضحة في الملف المرفوع."
        ),
        expected_llm_output_format=ExpectedLLMOutputFormat(
            type="text",
            must_be_grounded=True,
            must_not_use_general_knowledge=True
        )
    )

    api_key_pool._keys["FAST"] = [APIKey("gsk_test", "FAST_KEY_1")]

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value={
        "text": "Supervised learning uses labeled dataset inputs.",
        "input_tokens": 10,
        "output_tokens": 5,
        "latency_ms": 100
    })

    service = GenerationService(provider=mock_provider)
    response = await service.execute_task(payload)

    assert response.status == "success"
    assert "labeled dataset" in response.output_text
    assert response.source_chunk_ids == ["chunk_a"]

@pytest.mark.asyncio
async def test_generation_service_json_repair_retry():
    payload = LLMEngineerPayload(
        task_id="task_3",
        task_type="quiz_generation",
        pipeline_type="standard_rag",
        original_user_query="Generate a quiz",
        source=SourceInfo(source_id="doc_1", source_type="document"),
        retrieved_document_context=[
            ChunkContext(chunk_id="chunk_a", page_number=1, content="This is study material.")
        ],
        strict_grounding_policy=StrictGroundingPolicy(
            academic_source_of_truth="retrieved_document_context_only",
            memory_usage="personalization_only",
            if_document_context_insufficient="لم أجد إجابة واضحة في الملف المرفوع."
        ),
        expected_llm_output_format=ExpectedLLMOutputFormat(
            type="quiz_json",
            question_count=1,
            must_be_grounded=True,
            must_not_use_general_knowledge=True
        )
    )

    api_key_pool._keys["REASONING"] = [APIKey("gsk_test_reasoning", "REASONING_KEY_1")]

    # First call returns broken JSON, second call returns correct JSON
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(side_effect=[
        {"text": "Here is quiz: { broken_json ", "input_tokens": 10, "output_tokens": 5, "latency_ms": 100},
        {"text": '{"quiz_title": "Math Quiz", "difficulty": "medium", "questions": [{"question": "1+1?", "type": "mcq", "options": ["1", "2", "3", "4"], "correct_answer": "2", "explanation": "arithmetic", "source_chunk_ids": ["chunk_a"]}]}', "input_tokens": 15, "output_tokens": 20, "latency_ms": 150}
    ])

    service = GenerationService(provider=mock_provider)
    response = await service.execute_task(payload)

    assert response.status == "success"
    assert response.output_json is not None
    assert response.output_json["quiz_title"] == "Math Quiz"
    assert mock_provider.generate.call_count == 2
