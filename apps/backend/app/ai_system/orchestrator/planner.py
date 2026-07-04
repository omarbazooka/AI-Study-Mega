import re
from typing import List, Dict, Any
from app.schemas.ai_schema import PDFChatRequest, ExecutionPlan, Task
from app.ai_system.orchestrator.constants import (
    TASK_CHAT_ANSWER,
    TASK_EXPLAIN,
    TASK_SUMMARY,
    TASK_QUIZ,
    TASK_ANSWER_TABLE,
    TASK_KEY_POINTS,
    TASK_COMPARISON_TABLE,
    TASK_UNKNOWN,
    MODE_SINGLE,
    MODE_PARALLEL,
    MODE_SEQUENTIAL,
    KEYWORDS,
    CLARIFICATION_QUESTION_AR,
    CLARIFICATION_QUESTION_EN
)
from app.ai_system.orchestrator.errors import PlanningError

class TaskPlanner:
    """
    Planner module that parses user inputs, detects intents in English and Arabic,
    resolves dependencies between compound requests, and outputs an ExecutionPlan.
    """

    def __init__(self):
        # Setup regex splitting for compound requests using connectors
        # Handles: Arabic 'و', 'ثم' and English 'and', 'then' as well as punctuation like commas
        self.split_regex = re.compile(
            r'\s+(?:and|then|ثم)\s+|[\,،\+]\s*|(?:\s+و\s+)',
            re.IGNORECASE
        )
        
        # Simple greetings to trigger clarification for vague queries
        self.greetings = {
            "hi", "hello", "hey", "hola", "مرحبا", "اهلا", "أهلاً", "سلام", "صباح الخير", "مساء الخير"
        }

    def plan(self, request: Any) -> ExecutionPlan:
        """
        Generates an ExecutionPlan based on the request (PDFChatRequest, SummaryRequest, or QuizRequest).
        """
        # Handle Shortcut Requests
        if hasattr(request, "summary_style"):  # SummaryRequest shortcut
            metadata = {}
            if getattr(request, "summary_style", None):
                metadata["summary_style"] = request.summary_style
            
            task = Task(
                task_id="task_1",
                type=TASK_SUMMARY,
                query="Generate a summary of the document",
                metadata=metadata
            )
            return ExecutionPlan(
                execution_mode=MODE_SINGLE,
                confidence=1.0,
                needs_clarification=False,
                tasks=[task]
            )

        if hasattr(request, "difficulty"):  # QuizRequest shortcut
            metadata = {
                "difficulty": getattr(request, "difficulty", "medium"),
                "number_of_questions": getattr(request, "number_of_questions", 5),
                "question_type": getattr(request, "question_type", "multiple_choice")
            }
            task = Task(
                task_id="task_1",
                type=TASK_QUIZ,
                query="Generate a quiz from the document",
                metadata=metadata
            )
            return ExecutionPlan(
                execution_mode=MODE_SINGLE,
                confidence=1.0,
                needs_clarification=False,
                tasks=[task]
            )

        # Handle Chat Request
        if not isinstance(request, PDFChatRequest):
            raise PlanningError("Invalid request object type passed to TaskPlanner.")

        message = request.message.strip()
        lang = request.language if request.language in ["ar", "en"] else "ar"

        # Check for empty or vague requests / greetings
        cleaned_msg = re.sub(r'[^\w\s]', '', message).lower().strip()
        if len(message) < 3 or cleaned_msg in self.greetings:
            question = CLARIFICATION_QUESTION_AR if lang == "ar" else CLARIFICATION_QUESTION_EN
            return ExecutionPlan(
                execution_mode=MODE_SINGLE,
                confidence=1.0,
                needs_clarification=True,
                clarification_question=question,
                tasks=[]
            )

        # Detect intents
        detected_intents = self._detect_intents(message)

        # If no explicit intent keywords are matched, default to standard chat grounding
        if not detected_intents:
            task = Task(
                task_id="task_1",
                type=TASK_CHAT_ANSWER,
                query=message,
                metadata={}
            )
            return ExecutionPlan(
                execution_mode=MODE_SINGLE,
                confidence=1.0,
                needs_clarification=False,
                tasks=[task]
            )

        # Handle single intent
        if len(detected_intents) == 1:
            intent = list(detected_intents)[0]
            task = Task(
                task_id="task_1",
                type=intent,
                query=message,
                metadata={}
            )
            return ExecutionPlan(
                execution_mode=MODE_SINGLE,
                confidence=1.0,
                needs_clarification=False,
                tasks=[task]
            )

        # Handle compound intent (multiple intents detected)
        parts = [p.strip() for p in self.split_regex.split(message) if p.strip()]
        tasks: List[Task] = []
        task_id_counter = 1

        # We want to associate each detected intent with a corresponding split sentence if possible
        # Or fall back to using the full message query if splitting didn't produce clean components
        for intent in detected_intents:
            task_query = message  # Default fallback
            
            # Search split parts for the one containing the intent keywords
            for part in parts:
                part_intents = self._detect_intents(part)
                if intent in part_intents:
                    task_query = part
                    break
            
            tasks.append(
                Task(
                    task_id=f"task_{task_id_counter}",
                    type=intent,
                    query=task_query,
                    metadata={}
                )
            )
            task_id_counter += 1

        # Resolve Dependencies (e.g., answer_table depends on quiz)
        quiz_task = next((t for t in tasks if t.type == TASK_QUIZ), None)
        ans_table_task = next((t for t in tasks if t.type == TASK_ANSWER_TABLE), None)

        if ans_table_task and quiz_task:
            ans_table_task.depends_on.append(quiz_task.task_id)

        # Determine execution mode based on dependencies
        has_dependencies = any(len(t.depends_on) > 0 for t in tasks)
        mode = MODE_SEQUENTIAL if has_dependencies else MODE_PARALLEL

        return ExecutionPlan(
            execution_mode=mode,
            confidence=1.0,
            needs_clarification=False,
            tasks=tasks
        )

    def _detect_intents(self, text: str) -> set:
        """Helper to scan a string and return all matching intent types."""
        detected = set()
        text_lower = text.lower()
        
        # Check both Arabic and English keywords case-insensitively
        for lang in ["ar", "en"]:
            for intent, keywords in KEYWORDS[lang].items():
                for keyword in keywords:
                    # Simple keyword presence check
                    if keyword.lower() in text_lower:
                        detected.add(intent)
                        break
        return detected
