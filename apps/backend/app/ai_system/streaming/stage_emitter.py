import contextvars
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List, Union
from .stage_events import AIStageEvent, PublicAIStage, StageStatus

# ContextVar for callback: Callable[[AIStageEvent], None]
_current_emitter = contextvars.ContextVar("current_emitter", default=None)
_current_request_id = contextvars.ContextVar("current_request_id", default=None)

def set_current_emitter(request_id: str, callback: Callable[[AIStageEvent], None]):
    _current_request_id.set(request_id)
    _current_emitter.set(callback)

def clear_current_emitter():
    _current_request_id.set(None)
    _current_emitter.set(None)

def get_current_request_id() -> Optional[str]:
    return _current_request_id.get()

async def emit_stage_event(
    stage: PublicAIStage,
    status: StageStatus,
    message: Optional[str] = None,
    progress: float = 0.0,
    node_id: Optional[str] = None,
    content: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    callback = _current_emitter.get()
    request_id = _current_request_id.get()
    if callback and request_id:
        # Sanitize metadata to avoid leaking sensitive fields
        sanitized_meta = None
        if metadata:
            # List of allowed metadata keys
            allowed_keys = {
                "task_type", "question_count", "summary_style", "difficulty",
                "candidate_count", "selected_source_count", "cited_source_count",
                "page_numbers", "retry_count", "execution_mode",
                "completed_task_count", "total_task_count", "public_request_summary"
            }
            sanitized_meta = {k: v for k, v in metadata.items() if k in allowed_keys}

        event = AIStageEvent(
            request_id=request_id,
            node_id=node_id,
            stage=stage,
            status=status,
            label_key=f"ai_stage.{stage.value}",
            message=message,
            progress=progress,
            timestamp=datetime.now(timezone.utc).isoformat(),
            content=content,
            citations=citations,
            confidence=confidence,
            metadata=sanitized_meta
        )
        import asyncio
        if asyncio.iscoroutinefunction(callback):
            await callback(event)
        else:
            callback(event)
