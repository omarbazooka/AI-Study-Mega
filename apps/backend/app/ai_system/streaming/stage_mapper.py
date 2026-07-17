from typing import Dict, Any, Optional
from app.schemas.ai_schema import Task, TaskType
from .stage_events import PublicAIStage

def map_task_type_to_stage(task_type: TaskType) -> PublicAIStage:
    mapping = {
        TaskType.CHAT_ANSWER: PublicAIStage.GENERATION,
        TaskType.EXPLAIN: PublicAIStage.GENERATION,
        TaskType.SUMMARY: PublicAIStage.GENERATION,
        TaskType.QUIZ: PublicAIStage.QUIZ_GENERATION,
        TaskType.KEY_POINTS: PublicAIStage.GENERATION,
        TaskType.COMPARISON_TABLE: PublicAIStage.GENERATION,
        TaskType.ANSWER_TABLE: PublicAIStage.GENERATION,
        TaskType.FLASHCARDS: PublicAIStage.GENERATION,
        TaskType.ANSWER_EVALUATION: PublicAIStage.GENERATION,
    }
    return mapping.get(task_type, PublicAIStage.GENERATION)

def get_stage_message(stage: PublicAIStage, task: Optional[Task] = None, request: Optional[Any] = None) -> str:
    if stage == PublicAIStage.REQUEST_RECEIVED:
        return "Receiving your request"
    elif stage == PublicAIStage.DOCUMENT_CHECK:
        return "Checking the selected document"
    elif stage == PublicAIStage.INPUT_ANALYSIS:
        return "Understanding your request"
    elif stage == PublicAIStage.PLANNING:
        return "Planning the best response"
    elif stage == PublicAIStage.PERSONALIZATION:
        return "Adapting the response"
    elif stage == PublicAIStage.QUERY_PREPARATION:
        return "Preparing the document search"
    elif stage == PublicAIStage.RETRIEVAL:
        return "Searching the selected document"
    elif stage == PublicAIStage.RERANKING:
        return "Selecting the most relevant sources"
    elif stage == PublicAIStage.CONTEXT_BUILDING:
        return "Preparing the evidence"
    elif stage == PublicAIStage.VERIFICATION:
        return "Checking accuracy and document grounding"
    elif stage == PublicAIStage.CITATIONS:
        return "Preparing document citations"
    elif stage == PublicAIStage.REFINING:
        return "Refining the response"
    elif stage == PublicAIStage.FINALIZING:
        return "Finalizing the response"
    elif stage == PublicAIStage.COMPLETED:
        return "Response ready"
    elif stage == PublicAIStage.FAILED:
        return "Unable to complete the response"
    elif stage == PublicAIStage.CANCELLED:
        return "Request cancelled"

    # Default fallback for generation/quiz_generation based on task
    if task:
        ttype = task.type
        if ttype == TaskType.CHAT_ANSWER:
            return "Writing the answer"
        elif ttype == TaskType.EXPLAIN:
            return "Writing the explanation"
        elif ttype == TaskType.SUMMARY:
            size = getattr(request, "summary_size", "medium") if request else "medium"
            if size == "concise":
                return "Creating a concise summary"
            elif size == "detailed":
                return "Creating a detailed summary"
            return "Creating the summary"
        elif ttype == TaskType.QUIZ:
            q_count = getattr(request, "question_count", 5) if request else 5
            return f"Creating {q_count} quiz questions"
        elif ttype == TaskType.COMPARISON_TABLE:
            return "Building the comparison"
        elif ttype == TaskType.FLASHCARDS:
            return "Creating flashcards"
        elif ttype == TaskType.ANSWER_EVALUATION:
            return "Evaluating your answer"

    return "Writing the response"
