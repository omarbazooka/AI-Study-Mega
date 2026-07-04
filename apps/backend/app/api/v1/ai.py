from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.ai_schema import PDFChatRequest, SummaryRequest, QuizRequest, AIResponse
from app.ai_system.orchestrator import (
    TaskPlanner,
    TaskOrchestrator,
    validate_document_access,
    DocumentNotFoundError,
    DocumentAccessDeniedError,
    DocumentNotReadyError,
    PlanningError,
    AllTasksFailedError
)

router = APIRouter(prefix="/documents", tags=["ai"])

# Reuse user resolution placeholder mechanism from documents.py
MOCK_USER_ID = "00000000-0000-0000-0000-000000000000"

async def get_current_user() -> str:
    """
    TODO: Integrate this placeholder with the actual Supabase JWT authentication system
    to retrieve the authenticated user's ID from tokens.
    """
    return MOCK_USER_ID

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
    # TODO: user_id should come from authenticated user context (current_user_id) rather than body
    try:
        # Validate existence, ownership, and ingestion status
        await validate_document_access(document_id, request.user_id)
        
        # Initialize Planner & Orchestrator
        planner = TaskPlanner()
        orchestrator = TaskOrchestrator()
        
        # Build plan
        plan = planner.plan(request)
        
        # Execute & return merged response
        response = await orchestrator.execute(plan, request)
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
    except PlanningError as pe:
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
    # TODO: user_id should come from authenticated user context (current_user_id) rather than body
    try:
        await validate_document_access(document_id, request.user_id)
        
        planner = TaskPlanner()
        orchestrator = TaskOrchestrator()
        
        plan = planner.plan(request)
        response = await orchestrator.execute(plan, request)
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
    # TODO: user_id should come from authenticated user context (current_user_id) rather than body
    try:
        await validate_document_access(document_id, request.user_id)
        
        planner = TaskPlanner()
        orchestrator = TaskOrchestrator()
        
        plan = planner.plan(request)
        response = await orchestrator.execute(plan, request)
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
