from typing import List, Dict, Any, Optional
import logging
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
supabase = get_supabase_client()

async def create_chat_session(user_id: str, session_id: str, document_id: Optional[str] = None) -> Dict[str, Any]:
    """Creates a new chat session in PostgreSQL."""
    logger.info(f"[DB] Creating chat session {session_id} for user {user_id} with document_id {document_id}")
    
    # Check if session already exists
    existing = supabase.table("chat_sessions").select("*").eq("id", session_id).execute()
    if existing.data:
        return existing.data[0]
        
    row = {
        "id": session_id,
        "user_id": user_id
    }
    if document_id:
        row["document_id"] = document_id
        
    response = supabase.table("chat_sessions").insert(row).execute()
    return response.data[0] if response.data else {}

async def get_chat_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Gets a chat session by id."""
    response = supabase.table("chat_sessions").select("*").eq("id", session_id).execute()
    return response.data[0] if response.data else None

async def update_chat_session_title(session_id: str, title: str) -> Dict[str, Any]:
    """Updates the title of a chat session in PostgreSQL."""
    logger.info(f"[DB] Updating chat session {session_id} title to: {title}")
    response = supabase.table("chat_sessions").update({"title": title}).eq("id", session_id).execute()
    return response.data[0] if response.data else {}

async def save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    topic: Optional[str] = None,
    retrieved_chunks: List[str] = None,
    source_chunk_id: Optional[str] = None,
    metadata: Dict[str, Any] = None,
    token_usage: Dict[str, Any] = None,
    document_id: Optional[str] = None
) -> Dict[str, Any]:
    """Saves a message (user or assistant) in PostgreSQL."""
    logger.info(f"[DB] Saving {role} message to session {session_id}")
    
    # Ensure session exists first
    await create_chat_session(user_id, session_id, document_id)
    
    # If this is the first message of the session, generate and save title in background
    if role == "user" and content:
        session = await get_chat_session(session_id)
        if session and not session.get("title"):
            import asyncio
            async def _bg_title_gen():
                try:
                    from app.ai_system.services.llm.generation_service import GenerationService
                    gen_service = GenerationService()
                    title = await gen_service.generate_chat_title(content)
                    if title:
                        await update_chat_session_title(session_id, title)
                except Exception as e:
                    logger.error(f"Failed to generate/save chat title in background: {e}")
            
            asyncio.create_task(_bg_title_gen())

    row = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
    }
    if topic:
        row["topic"] = topic
    if retrieved_chunks:
        row["retrieved_chunks"] = retrieved_chunks
    if source_chunk_id:
        row["source_chunk_id"] = source_chunk_id
    if metadata:
        row["metadata"] = metadata
    if token_usage:
        row["token_usage"] = token_usage
        
    response = supabase.table("messages").insert(row).execute()
    return response.data[0] if response.data else {}

async def get_session_messages(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves message history for a session ordered by created_at ascending."""
    response = (
        supabase.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return response.data or []

async def get_document_sessions(user_id: str, document_id: str) -> List[Dict[str, Any]]:
    """Retrieves all non-empty chat sessions for a specific user and document, ordered by updated_at descending, including title."""
    response = (
        supabase.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .eq("document_id", document_id)
        .order("updated_at", desc=True)
        .execute()
    )
    sessions = response.data or []
    if not sessions:
        return []
        
    session_ids = [s["id"] for s in sessions]
    messages_resp = (
        supabase.table("messages")
        .select("session_id, content, created_at")
        .in_("session_id", session_ids)
        .eq("role", "user")
        .order("created_at", desc=False)
        .execute()
    )
    
    first_msgs = {}
    for m in (messages_resp.data or []):
        sid = m["session_id"]
        if sid not in first_msgs:
            first_msgs[sid] = m["content"]
            
    results = []
    for s in sessions:
        # Filter out empty sessions
        if s["id"] not in first_msgs:
            continue
            
        title = s.get("title")
        if not title or title.strip() == "":
            raw_title = first_msgs.get(s["id"], "New Chat")
            title = raw_title[:50] + "..." if len(raw_title) > 50 else raw_title
            
        results.append({
            **s,
            "title": title
        })
    return results
