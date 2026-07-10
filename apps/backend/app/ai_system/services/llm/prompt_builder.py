from .prompts.chat_prompt import CHAT_PROMPT_TEMPLATE
from .prompts.summary_prompt import SUMMARY_MAP_TEMPLATE, SUMMARY_REDUCE_TEMPLATE
from .prompts.quiz_prompt import QUIZ_PROMPT_TEMPLATE
from .prompts.explanation_prompt import EXPLANATION_PROMPT_TEMPLATE
from .prompts.evaluation_prompt import EVALUATION_PROMPT_TEMPLATE
from .prompts.verifier_prompt import VERIFIER_PROMPT_TEMPLATE

class PromptBuilder:
    """Builder class to dynamically build formatted prompt strings for tasks."""

    @staticmethod
    def build_chat_prompt(context: str, question: str, history: str = "") -> str:
        return CHAT_PROMPT_TEMPLATE.format(context=context, question=question, history=history or "No prior conversation.")


    @staticmethod
    def build_summary_map_prompt(chunks: str) -> str:
        return SUMMARY_MAP_TEMPLATE.format(chunks=chunks)

    @staticmethod
    def build_summary_reduce_prompt(concepts: str) -> str:
        return SUMMARY_REDUCE_TEMPLATE.format(concepts=concepts)

    @staticmethod
    def build_quiz_prompt(context: str, num_questions: int, difficulty: str) -> str:
        return QUIZ_PROMPT_TEMPLATE.format(
            context=context,
            num_questions=num_questions,
            difficulty=difficulty
        )

    @staticmethod
    def build_explanation_prompt(context: str, topic: str) -> str:
        return EXPLANATION_PROMPT_TEMPLATE.format(context=context, topic=topic)

    @staticmethod
    def build_evaluation_prompt(
        context: str,
        question: str,
        expected_answer: str,
        student_answer: str
    ) -> str:
        return EVALUATION_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
            expected_answer=expected_answer,
            student_answer=student_answer
        )

    @staticmethod
    def build_verifier_prompt(context: str, response: str) -> str:
        return VERIFIER_PROMPT_TEMPLATE.format(context=context, response=response)
