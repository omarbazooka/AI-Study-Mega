from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple
from .exceptions import LLMConfigurationError

class LLMProfile(str, Enum):
    PLANNING = "planning"
    MEMORY_MAP = "memory_map"
    EXECUTION_REDUCE = "execution_reduce"
    VERIFICATION = "verification"
    QUIZ = "quiz"

class LLMRole(str, Enum):
    # Planning roles
    PLANNER = "planner"
    INTENT_CLASSIFIER = "intent_classifier"
    TASK_DECOMPOSER = "task_decomposer"
    DAG_BUILDER = "dag_builder"
    QUERY_REWRITER = "query_rewriter"
    SELF_QUERY_FILTER = "self_query_filter"
    
    # Memory / Map roles
    MEMORY_SUMMARIZER = "memory_summarizer"
    CONVERSATION_SUMMARIZER = "conversation_summarizer"
    PERSONALIZATION_BUILDER = "personalization_builder"
    MAP_WORKER = "map_worker"
    
    # Execution / Reduce roles
    EXECUTOR = "executor"
    EXPLANATION_GENERATOR = "explanation_generator"
    COMPARISON_GENERATOR = "comparison_generator"
    TABLE_GENERATOR = "table_generator"
    REDUCE_WORKER = "reduce_worker"
    RESPONSE_MERGER = "response_merger"
    CHAT_GENERATOR = "chat_generator"
    
    # Verification roles
    VERIFIER = "verifier"
    GROUNDEDNESS_CHECKER = "groundedness_checker"
    CITATION_CHECKER = "citation_checker"
    COMPLETENESS_CHECKER = "completeness_checker"
    ANSWER_EVALUATOR = "answer_evaluator"
    
    # Quiz roles
    QUIZ_PLANNER = "quiz_planner"
    QUIZ_GENERATOR = "quiz_generator"
    DISTRACTOR_GENERATOR = "distractor_generator"
    QUIZ_EXPLANATION_GENERATOR = "quiz_explanation_generator"


ROLE_PROFILE_MAP: Dict[LLMRole, LLMProfile] = {
    LLMRole.PLANNER: LLMProfile.PLANNING,
    LLMRole.INTENT_CLASSIFIER: LLMProfile.PLANNING,
    LLMRole.TASK_DECOMPOSER: LLMProfile.PLANNING,
    LLMRole.DAG_BUILDER: LLMProfile.PLANNING,
    LLMRole.QUERY_REWRITER: LLMProfile.PLANNING,
    LLMRole.SELF_QUERY_FILTER: LLMProfile.PLANNING,
    
    LLMRole.MEMORY_SUMMARIZER: LLMProfile.MEMORY_MAP,
    LLMRole.CONVERSATION_SUMMARIZER: LLMProfile.MEMORY_MAP,
    LLMRole.PERSONALIZATION_BUILDER: LLMProfile.MEMORY_MAP,
    LLMRole.MAP_WORKER: LLMProfile.MEMORY_MAP,
    
    LLMRole.EXECUTOR: LLMProfile.EXECUTION_REDUCE,
    LLMRole.EXPLANATION_GENERATOR: LLMProfile.EXECUTION_REDUCE,
    LLMRole.COMPARISON_GENERATOR: LLMProfile.EXECUTION_REDUCE,
    LLMRole.TABLE_GENERATOR: LLMProfile.EXECUTION_REDUCE,
    LLMRole.REDUCE_WORKER: LLMProfile.EXECUTION_REDUCE,
    LLMRole.RESPONSE_MERGER: LLMProfile.EXECUTION_REDUCE,
    LLMRole.CHAT_GENERATOR: LLMProfile.EXECUTION_REDUCE,
    
    LLMRole.VERIFIER: LLMProfile.VERIFICATION,
    LLMRole.GROUNDEDNESS_CHECKER: LLMProfile.VERIFICATION,
    LLMRole.CITATION_CHECKER: LLMProfile.VERIFICATION,
    LLMRole.COMPLETENESS_CHECKER: LLMProfile.VERIFICATION,
    LLMRole.ANSWER_EVALUATOR: LLMProfile.VERIFICATION,
    
    LLMRole.QUIZ_PLANNER: LLMProfile.QUIZ,
    LLMRole.QUIZ_GENERATOR: LLMProfile.QUIZ,
    LLMRole.DISTRACTOR_GENERATOR: LLMProfile.QUIZ,
    LLMRole.QUIZ_EXPLANATION_GENERATOR: LLMProfile.QUIZ,
}

ROLE_MODEL_OVERRIDE_MAP: Dict[LLMRole, str] = {
    LLMRole.PLANNER: "GROQ_PLANNER_MODEL",
    LLMRole.QUERY_REWRITER: "GROQ_QUERY_REWRITER_MODEL",
    LLMRole.MEMORY_SUMMARIZER: "GROQ_MEMORY_MODEL",
    LLMRole.CONVERSATION_SUMMARIZER: "GROQ_MEMORY_MODEL",
    LLMRole.PERSONALIZATION_BUILDER: "GROQ_MEMORY_MODEL",
    LLMRole.MAP_WORKER: "GROQ_MAP_MODEL",
    LLMRole.EXECUTOR: "GROQ_EXECUTOR_MODEL",
    LLMRole.CHAT_GENERATOR: "GROQ_EXECUTOR_MODEL",
    LLMRole.EXPLANATION_GENERATOR: "GROQ_EXECUTOR_MODEL",
    LLMRole.COMPARISON_GENERATOR: "GROQ_EXECUTOR_MODEL",
    LLMRole.TABLE_GENERATOR: "GROQ_EXECUTOR_MODEL",
    LLMRole.REDUCE_WORKER: "GROQ_REDUCE_MODEL",
    LLMRole.RESPONSE_MERGER: "GROQ_REDUCE_MODEL",
    LLMRole.VERIFIER: "GROQ_VERIFIER_MODEL",
    LLMRole.GROUNDEDNESS_CHECKER: "GROQ_VERIFIER_MODEL",
    LLMRole.CITATION_CHECKER: "GROQ_VERIFIER_MODEL",
    LLMRole.COMPLETENESS_CHECKER: "GROQ_VERIFIER_MODEL",
    LLMRole.ANSWER_EVALUATOR: "GROQ_EVALUATOR_MODEL",
    LLMRole.QUIZ_PLANNER: "GROQ_QUIZ_GENERATOR_MODEL",
    LLMRole.QUIZ_GENERATOR: "GROQ_QUIZ_GENERATOR_MODEL",
    LLMRole.DISTRACTOR_GENERATOR: "GROQ_QUIZ_GENERATOR_MODEL",
    LLMRole.QUIZ_EXPLANATION_GENERATOR: "GROQ_QUIZ_GENERATOR_MODEL",
}

TASK_ROLE_MAP: Dict[str, LLMRole] = {
    "query_rewrite": LLMRole.QUERY_REWRITER,
    "intent_detection": LLMRole.INTENT_CLASSIFIER,
    "chat_simple": LLMRole.CHAT_GENERATOR,
    "chat_complex": LLMRole.EXECUTOR,
    "summary_map": LLMRole.MAP_WORKER,
    "summary_reduce": LLMRole.REDUCE_WORKER,
    "quiz_generation": LLMRole.QUIZ_GENERATOR,
    "answer_evaluation": LLMRole.ANSWER_EVALUATOR,
    "verifier": LLMRole.VERIFIER,
    
    # Orchestrator Task String mappings
    "chat_answer": LLMRole.CHAT_GENERATOR,
    "explain": LLMRole.EXPLANATION_GENERATOR,
    "summary": LLMRole.MAP_WORKER,
    "quiz": LLMRole.QUIZ_GENERATOR,
    "key_points": LLMRole.MAP_WORKER,
    "comparison_table": LLMRole.COMPARISON_GENERATOR,
    "answer_table": LLMRole.TABLE_GENERATOR,
}


def resolve_config_for_role(role: LLMRole) -> Tuple[str, str]:
    """
    Resolves the API Key and model name configuration for a specific role.
    Resolution Order for Keys:
      1. GROQ_<PROFILE>_API_KEY
      2. GROQ_DEFAULT_API_KEY
    Resolution Order for Models:
      1. Role override model (if configured)
      2. Profile default model (if configured)
      3. GROQ_DEFAULT_MODEL
    """
    from app.core.config import settings
    profile = ROLE_PROFILE_MAP.get(role)
    if not profile:
        raise LLMConfigurationError(f"Unsupported LLM Role: '{role}'")

    # 1. API Key resolution
    key_attr = f"GROQ_{profile.value.upper()}_API_KEY"
    api_key = getattr(settings, key_attr, "").strip()
    if not api_key:
        api_key = settings.GROQ_DEFAULT_API_KEY.strip()

    if not api_key:
        raise LLMConfigurationError(f"No API key configured for profile '{profile.value}' and default key is empty.")

    # 2. Model resolution
    model_name = ""
    override_attr = ROLE_MODEL_OVERRIDE_MAP.get(role)
    if override_attr:
        model_name = getattr(settings, override_attr, "").strip()

    if not model_name:
        profile_model_attr = f"GROQ_{profile.value.upper()}_MODEL"
        model_name = getattr(settings, profile_model_attr, "").strip()

    if not model_name:
        model_name = settings.GROQ_DEFAULT_MODEL.strip()

    if not model_name:
        raise LLMConfigurationError(f"Could not resolve model for role '{role.value}' and default model is empty.")

    return api_key, model_name


@dataclass
class RoutedModelConfig:
    model_name: str
    key_group: str


class ModelRouter:
    """Task-based router that maps task type strings to LLMRole config structures."""

    @classmethod
    def route_task(cls, task_type: str) -> RoutedModelConfig:
        task_type_lower = task_type.lower()
        role = TASK_ROLE_MAP.get(task_type_lower)
        if not role:
            raise ValueError(f"Unknown task type: '{task_type}'")

        # Resolve config parameters for the corresponding role
        _, model_name = resolve_config_for_role(role)
        profile = ROLE_PROFILE_MAP[role]
        profile_upper = profile.value.upper()

        # Backward compatibility translation for unit tests
        legacy_mapping = {
            "PLANNING": "FAST",
            "MEMORY_MAP": "SUMMARY",
            "EXECUTION_REDUCE": "REASONING",
            "VERIFICATION": "VERIFIER",
            "QUIZ": "REASONING"
        }
        legacy_group = legacy_mapping.get(profile_upper, profile_upper)

        return RoutedModelConfig(model_name=model_name, key_group=legacy_group)
