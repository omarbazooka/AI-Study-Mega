from dataclasses import dataclass
from .config import LLMConfig

@dataclass
class RoutedModelConfig:
    model_name: str
    key_group: str

class ModelRouter:
    """Task-based router that maps AI task types to correct models and key pool groups."""

    TASK_MAPPING = {
        # Original task mappings
        "query_rewrite": ("FAST", LLMConfig.DEFAULT_FAST_MODEL),
        "intent_detection": ("FAST", LLMConfig.DEFAULT_FAST_MODEL),
        "chat_simple": ("FAST", LLMConfig.DEFAULT_FAST_MODEL),
        "chat_complex": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "summary_map": ("SUMMARY", LLMConfig.DEFAULT_SUMMARY_MODEL),
        "summary_reduce": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "quiz_generation": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "answer_evaluation": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "verifier": ("VERIFIER", LLMConfig.DEFAULT_VERIFIER_MODEL),
        
        # New orchestrator task mappings
        "chat_answer": ("FAST", LLMConfig.DEFAULT_FAST_MODEL),
        "explain": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "summary": ("SUMMARY", LLMConfig.DEFAULT_SUMMARY_MODEL),
        "quiz": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "key_points": ("SUMMARY", LLMConfig.DEFAULT_SUMMARY_MODEL),
        "comparison_table": ("REASONING", LLMConfig.DEFAULT_REASONING_MODEL),
        "answer_table": ("FAST", LLMConfig.DEFAULT_FAST_MODEL),
    }

    @classmethod
    def route_task(cls, task_type: str) -> RoutedModelConfig:
        """
        Routes the given task type to its corresponding model and key pool group.
        Raises ValueError if the task type is unknown.
        """
        task_type_lower = task_type.lower()
        if task_type_lower in cls.TASK_MAPPING:
            key_group, model_name = cls.TASK_MAPPING[task_type_lower]
            return RoutedModelConfig(model_name=model_name, key_group=key_group)
        
        raise ValueError(f"Unknown task type: '{task_type}'")
