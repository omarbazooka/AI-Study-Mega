import pytest
from app.ai_system.services.llm.model_router import ModelRouter

def test_model_router_mappings():
    # Test valid keys routing
    config_rewrite = ModelRouter.route_task("query_rewrite")
    assert config_rewrite.key_group == "FAST"
    
    config_quiz = ModelRouter.route_task("quiz_generation")
    assert config_quiz.key_group == "REASONING"

    config_eval = ModelRouter.route_task("answer_evaluation")
    assert config_eval.key_group == "VERIFIER"

    # Test orchestrator task mappings
    config_chat = ModelRouter.route_task("chat_answer")
    assert config_chat.key_group == "REASONING"

    config_explain = ModelRouter.route_task("explain")
    assert config_explain.key_group == "REASONING"

def test_model_router_invalid_task_raises_exception():
    # Unknown task must raise ValueError
    with pytest.raises(ValueError):
        ModelRouter.route_task("invalid_random_task_type")
