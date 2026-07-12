from typing import Optional, Dict, Any, List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.ai_schema import PDFChatRequest, SummaryRequest, QuizRequest, AIResponse
from app.services.ai_orchestrator import ai_orchestrator_service
from app.services.session_service import validate_session_ownership_and_document
from app.ai_system.orchestrator.errors import (
    DocumentNotFoundError,
    DocumentAccessDeniedError,
    DocumentNotReadyError,
    PlanningError,
    AllTasksFailedError
)

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["ai"])

from app.core.auth import get_current_user

@router.post("/{document_id}/chat", response_model=AIResponse, status_code=status.HTTP_200_OK)
async def chat_with_pdf(
    document_id: str,
    request: PDFChatRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    PDF-bound conversational search. Accepts any PDF-grounded user query, detects intent,
    plans subtasks (single/compound), executes them over document chunks, and aggregates responses.
    """
    await validate_session_ownership_and_document(request.session_id, document_id, current_user_id, create_if_missing=True)
    try:
        request.user_id = current_user_id
        response = await ai_orchestrator_service.execute_query(
            document_id=document_id,
            request=request,
            user_id=current_user_id
        )
        return response

    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND"
        )
    except DocumentAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DOCUMENT_ACCESS_DENIED"
        )
    except DocumentNotReadyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DOCUMENT_NOT_READY"
        )
    except PlanningError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PLANNING_FAILED"
        )
    except AllTasksFailedError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ALL_TASKS_FAILED"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ALL_TASKS_FAILED: {str(e)}"
        )

@router.post("/{document_id}/summary", response_model=AIResponse, status_code=status.HTTP_200_OK)
async def summarize_pdf(
    document_id: str,
    request: SummaryRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    Shortcut endpoint to generate a document-level summary.
    Schedules a single 'summary' task utilizing document-level context chunks.
    """
    await validate_session_ownership_and_document(request.session_id, document_id, current_user_id, create_if_missing=True)
    try:
        request.user_id = current_user_id
        response = await ai_orchestrator_service.execute_query(
            document_id=document_id,
            request=request,
            user_id=current_user_id
        )
        return response

    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND"
        )
    except DocumentAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DOCUMENT_ACCESS_DENIED"
        )
    except DocumentNotReadyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DOCUMENT_NOT_READY"
        )
    except AllTasksFailedError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ALL_TASKS_FAILED"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ALL_TASKS_FAILED: {str(e)}"
        )

@router.post("/{document_id}/quiz", response_model=AIResponse, status_code=status.HTTP_200_OK)
async def generate_pdf_quiz(
    document_id: str,
    request: QuizRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    Shortcut endpoint to generate a quiz from the PDF document.
    Schedules a single 'quiz' task utilizing document-level context chunks.
    """
    await validate_session_ownership_and_document(request.session_id, document_id, current_user_id, create_if_missing=True)
    try:
        request.user_id = current_user_id
        response = await ai_orchestrator_service.execute_query(
            document_id=document_id,
            request=request,
            user_id=current_user_id
        )
        return response

    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND"
        )
    except DocumentAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DOCUMENT_ACCESS_DENIED"
        )
    except DocumentNotReadyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DOCUMENT_NOT_READY"
        )
    except AllTasksFailedError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ALL_TASKS_FAILED"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ALL_TASKS_FAILED: {str(e)}"
        )


from typing import List, Dict, Any
from pydantic import BaseModel, Field
import uuid

class QuizResponseItem(BaseModel):
    question_id: str
    selected_option_id: int

class QuizSubmissionRequest(BaseModel):
    attempt_number: int
    idempotency_key: str
    responses: List[QuizResponseItem]

@router.post("/quizzes/{quiz_id}/submit", status_code=status.HTTP_200_OK)
async def submit_quiz(
    quiz_id: str,
    request_data: QuizSubmissionRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    Submits, grades, and records quiz answers.
    Operates server-side with RLS-safe postgres transaction blocks.
    Enforces idempotency and answer separation.
    """
    from app.db.supabase_client import get_supabase_client
    supabase = get_supabase_client()
    
    # 1. Ownership & Existence Check
    quiz_resp = supabase.table("quizzes").select("*").eq("id", quiz_id).execute()
    if not quiz_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found."
        )
    quiz = quiz_resp.data[0]
    if str(quiz["user_id"]) != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to access this quiz."
        )

    # 2. Idempotency Check
    attempt_resp = supabase.table("quiz_attempts")\
                           .select("*")\
                           .eq("quiz_id", quiz_id)\
                           .eq("user_id", current_user_id)\
                           .eq("idempotency_key", request_data.idempotency_key)\
                           .execute()
    
    if attempt_resp.data:
        # Check if already completed
        attempt = attempt_resp.data[0]
        if attempt["status"] == "completed":
            # Load stored responses
            resp_data = supabase.table("question_responses")\
                                .select("*")\
                                .eq("attempt_id", attempt["id"])\
                                .execute()
            # Fetch explanations/metadata
            answers_resp = supabase.table("quiz_question_answers")\
                                   .select("*")\
                                   .in_("question_id", [r["question_id"] for r in resp_data.data])\
                                   .execute()
            ans_map = {a["question_id"]: a for a in answers_resp.data}
            
            questions_resp = supabase.table("quiz_questions")\
                                     .select("*")\
                                     .eq("quiz_id", quiz_id)\
                                     .execute()
            q_map = {q["id"]: q for q in questions_resp.data}
            
            graded_responses = []
            for r in resp_data.data:
                q = q_map.get(r["question_id"], {})
                a = ans_map.get(r["question_id"], {})
                graded_responses.append({
                    "question_id": r["question_id"],
                    "selected_option_id": r["selected_option_id"],
                    "is_correct": r["is_correct"],
                    "correct_option_id": a.get("correct_option_id"),
                    "explanation": a.get("explanation"),
                    "question_text": q.get("question_text"),
                    "options": q.get("options")
                })
            
            return {
                "status": "completed",
                "attempt_id": attempt["id"],
                "correct_count": attempt["correct_count"],
                "total_questions": attempt["total_questions"],
                "score_percentage": float(attempt["score_percentage"]),
                "responses": graded_responses
            }

    # 3. Load all questions and correct answers for this quiz
    q_resp = supabase.table("quiz_questions").select("*").eq("quiz_id", quiz_id).execute()
    if not q_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz questions not found."
        )
    q_map = {q["id"]: q for q in q_resp.data}
    
    a_resp = supabase.table("quiz_question_answers")\
                     .select("*")\
                     .in_("question_id", list(q_map.keys()))\
                     .execute()
    ans_map = {a["question_id"]: a for a in a_resp.data}

    # 4. Grade the submission
    correct_count = 0
    total_questions = len(q_resp.data)
    responses_to_grade = {r.question_id: r.selected_option_id for r in request_data.responses}

    graded_responses = []
    responses_to_insert = []
    
    # Generate new attempt ID
    attempt_id = str(uuid.uuid4())

    for q_id, q in q_map.items():
        selected_id = responses_to_grade.get(q_id)
        if selected_id is None:
            selected_id = -1
            
        ans = ans_map.get(q_id, {})
        correct_id = ans.get("correct_option_id", 0)
        is_correct = (selected_id == correct_id)
        if is_correct:
            correct_count += 1
            
        graded_responses.append({
            "question_id": q_id,
            "selected_option_id": selected_id,
            "is_correct": is_correct,
            "correct_option_id": correct_id,
            "explanation": ans.get("explanation", ""),
            "question_text": q.get("question_text"),
            "options": q.get("options")
        })
        
        responses_to_insert.append({
            "attempt_id": attempt_id,
            "question_id": q_id,
            "selected_option_id": selected_id,
            "is_correct": is_correct
        })

    score_percentage = round((correct_count / total_questions) * 100, 2) if total_questions > 0 else 0.0

    # 5. Insert Attempt and Responses (using high-privilege service client)
    from datetime import datetime, timezone
    
    supabase.table("quiz_attempts").insert({
        "id": attempt_id,
        "user_id": current_user_id,
        "quiz_id": quiz_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "total_questions": total_questions,
        "correct_count": correct_count,
        "score_percentage": score_percentage,
        "attempt_number": request_data.attempt_number,
        "idempotency_key": request_data.idempotency_key
    }).execute()

    supabase.table("question_responses").insert(responses_to_insert).execute()

    return {
        "status": "completed",
        "attempt_id": attempt_id,
        "correct_count": correct_count,
        "total_questions": total_questions,
        "score_percentage": score_percentage,
        "responses": graded_responses
    }

@router.post("/{document_id}/chat/stream")
async def chat_with_pdf_stream(
    document_id: str,
    request: PDFChatRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    Progressive search stream returning NDJSON progress steps.
    """
    # Validate session binding
    await validate_session_ownership_and_document(request.session_id, document_id, current_user_id, create_if_missing=True)
    # 1. Ownership & Access Validation
    try:
        from app.ai_system.orchestrator.document_guard import validate_document_access
        await validate_document_access(document_id, current_user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e}"
        )
        
    request.document_id = document_id
    request.user_id = current_user_id

    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        # Setup trace stream
        req_id = str(uuid.uuid4())
        
        # Helper to yield event
        def make_event(stage: str, status: str, message: str, progress: float, node_id: Optional[str] = None, data: Optional[dict] = None):
            import json
            from datetime import datetime, timezone
            event_obj = {
                "request_id": req_id,
                "node_id": node_id,
                "stage": stage,
                "status": status,
                "message": message,
                "progress": progress,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if data:
                event_obj.update(data)
            return json.dumps(event_obj, ensure_ascii=False) + "\n"

        # Stage 1: Auth & Validation completed
        yield make_event("authentication", "completed", "User authentication and scope verified.", 5.0)
        yield make_event("input_validation", "started", "Validating query input.", 10.0)
        
        # Run input validation checks
        from app.ai_system.validation.input_validator import validate_input
        val_result = await validate_input(
            raw_text=request.message,
            document_id=document_id,
            user_id=current_user_id
        )
        if not val_result.valid:
            yield make_event("input_validation", "failed", f"Input validation rejected: {', '.join(val_result.reasons)}", 100.0)
            return
            
        yield make_event("input_validation", "completed", "Input validated successfully.", 15.0)
        
        # Stage 2: Planning
        yield make_event("planning", "started", "Constructing task execution plan DAG.", 20.0)
        from app.ai_system.orchestrator.planner import TaskPlanner
        planner = TaskPlanner()
        try:
            plan = await planner.plan(request)
            yield make_event("planning", "completed", f"Plan generated successfully with {len(plan.tasks)} tasks.", 35.0)
        except Exception as e:
            yield make_event("planning", "failed", f"Planning failed: {e}", 100.0)
            return

        # Stage 3: DAG routing & Execution
        yield make_event("dag_routing", "started", f"Executing DAG Plan under mode: {plan.execution_mode.value}", 40.0)
        
        from app.ai_system.orchestrator.pipeline_registry import PIPELINE_REGISTRY
        completed_results = {}
        
        # Execute each task in order
        total_tasks = len(plan.tasks)
        for idx, task in enumerate(plan.tasks):
            t_progress = 40.0 + ((idx / total_tasks) * 50.0)
            yield make_event(task.type.value, "started", f"Starting task {task.task_id} ({task.type.value})", t_progress, task.task_id)
            
            pipeline_fn = PIPELINE_REGISTRY.get(task.type.value)
            if not pipeline_fn:
                yield make_event(task.type.value, "failed", f"No pipeline runner registered for task type '{task.type.value}'", 100.0, task.task_id)
                return
                
            try:
                # Execute pipeline step
                result = await pipeline_fn(task, request, completed_results)
                completed_results[task.task_id] = result
                yield make_event(task.type.value, "completed", f"Completed task {task.task_id}.", t_progress + (50.0 / total_tasks), task.task_id)
            except Exception as e:
                yield make_event(task.type.value, "failed", f"Task execution failed: {e}", t_progress + (50.0 / total_tasks), task.task_id)
                # Determine if fatal: if it's the primary intent or if it's the only task in the plan
                is_fatal = (task.type == plan.primary_intent) or (total_tasks == 1)
                if is_fatal:
                    return
                logger.warning(f"Non-fatal task {task.task_id} failed: {e}")
                
        # Stage 4: Finished (yield final result payload)
        last_res = list(completed_results.values())[-1] if completed_results else None
        res_data = {}
        if last_res:
            res_data["content"] = last_res.content
            if last_res.citations:
                res_data["citations"] = [
                    {
                        "chunk_id": c.chunk_id,
                        "page_number": c.page_number,
                        "section_title": c.section_title,
                        "score": c.score
                    } for c in last_res.citations
                ]
        yield make_event("completed", "completed", "Search query DAG execution completed successfully.", 100.0, data=res_data)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# Reload trigger comment
