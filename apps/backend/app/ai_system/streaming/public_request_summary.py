from typing import Any
from app.schemas.ai_schema import DAGPlan, TaskType

def build_public_request_summary(plan: DAGPlan, request: Any, language: str = "en") -> str:
    parts = []
    
    for task in plan.tasks:
        task_type = task.type
        query_text = task.query or ""
        clean_query = query_text.strip()
        
        if task_type == TaskType.CHAT_ANSWER:
            if clean_query:
                words = clean_query.split()
                if len(words) > 10:
                    clean_query = " ".join(words[:10]) + "..."
                parts.append(f"answer a question about '{clean_query}'")
            else:
                parts.append("answer a question about the selected document")
                
        elif task_type == TaskType.EXPLAIN:
            words = clean_query.split()
            if len(words) > 10:
                clean_query = " ".join(words[:10]) + "..."
            parts.append(f"explain '{clean_query}'")
            
        elif task_type == TaskType.SUMMARY:
            style = getattr(request, "summary_style", "paragraph") or "paragraph"
            size = getattr(request, "summary_size", "medium") or "medium"
            style_str = f"a {size} {style} summary"
            parts.append(f"create {style_str}")
            
        elif task_type == TaskType.QUIZ:
            q_count = getattr(request, "question_count", 5) or task.metadata.get("question_count", 5) or 5
            difficulty = getattr(request, "difficulty", "medium") or "medium"
            parts.append(f"create {q_count} {difficulty}-level quiz questions")
            
        elif task_type == TaskType.COMPARISON_TABLE:
            words = clean_query.split()
            if len(words) > 10:
                clean_query = " ".join(words[:10]) + "..."
            parts.append(f"compare '{clean_query}'")
            
        elif task_type == TaskType.FLASHCARDS:
            parts.append("create study flashcards")
            
        elif task_type == TaskType.ANSWER_EVALUATION:
            parts.append("evaluate your answer")
            
        elif task_type == TaskType.KEY_POINTS:
            parts.append("extract key points")

    if not parts:
        return "You're asking a question about the selected document."
        
    if len(parts) == 1:
        return f"You're asking me to {parts[0]} using the selected document."
    elif len(parts) == 2:
        return f"You're asking me to {parts[0]} and {parts[1]} using the selected document."
    else:
        joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"
        return f"You're asking me to {joined} using the selected document."
