import pytest

def validate_pipeline_output_schema(record):
    required_keys = {
        "test_case_id", "question", "actual_answer", "retrieved_contexts",
        "retrieved_chunk_ids", "retrieved_page_numbers", "retrieval_scores",
        "reranker_scores", "citations", "planner_intent", "execution_mode",
        "verifier_status", "verifier_action", "final_confidence", "model_provider",
        "model_name", "fallback_models_used", "prompt_version",
        "retrieval_latency_ms", "reranking_latency_ms", "planning_latency_ms",
        "generation_latency_ms", "verification_latency_ms", "total_latency_ms",
        "input_tokens", "output_tokens", "total_tokens", "error", "timestamp"
    }
    
    missing = required_keys - set(record.keys())
    assert not missing, f"Missing required keys in pipeline output: {missing}"

def test_pipeline_output_valid():
    record = {
        "test_case_id": "TC-001",
        "question": "What is semantic search?",
        "actual_answer": "Semantic search matches query intent rather than words.",
        "retrieved_contexts": ["chunk text 1"],
        "retrieved_chunk_ids": ["c1"],
        "retrieved_page_numbers": [3],
        "retrieval_scores": [0.91],
        "reranker_scores": [0.94],
        "citations": [],
        "planner_intent": "chat_answer",
        "execution_mode": "single",
        "verifier_status": "passed",
        "verifier_action": "pass",
        "final_confidence": 0.92,
        "model_provider": "groq",
        "model_name": "llama-3.3-70b-versatile",
        "fallback_models_used": [],
        "prompt_version": "v1.0",
        "retrieval_latency_ms": 200,
        "reranking_latency_ms": 150,
        "planning_latency_ms": 120,
        "generation_latency_ms": 1500,
        "verification_latency_ms": 400,
        "total_latency_ms": 2370,
        "input_tokens": 1200,
        "output_tokens": 150,
        "total_tokens": 1350,
        "error": None,
        "timestamp": "2026-07-13T18:30:00Z"
    }
    validate_pipeline_output_schema(record)
