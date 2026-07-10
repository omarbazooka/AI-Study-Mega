import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.ai_system.memory.memory_store import MemoryStore
from app.ai_system.memory.memory_types import MemoryContext, ChatMessage
from app.schemas.personalization_schema import UserProfile
from app.schemas.memory_schema import MemoryItem, WeakTopic, MistakePattern, TopicMastery
from app.ai_system.memory import memory_config

logger = logging.getLogger(__name__)

CONTINUATION_SIGNALS = [
    "continue", "go on", "explain more", "more detail", "tell me more",
    "what's next", "keep going", "elaborate",
    "expand on that", "go deeper", "what else",
    "أكمل", "استمر", "تفاصيل أكثر", "اشرح أكثر", "وضح أكثر"
]

_NEW_TOPIC_STARTERS = {
    "what", "why", "how", "when", "where", "who", "which",
    "define", "describe", "explain", "can you", "could you",
    "ما", "ماذا", "كيف", "لماذا", "متى", "أين", "من", "هل"
}

def detect_continuation(query: str) -> bool:
    """Returns True if user query implies a continuation of previous topic."""
    q = query.lower().strip()
    words = q.split()
    
    # Check explicitly if any continuation signals exist first
    if any(sig in q for sig in CONTINUATION_SIGNALS):
        return True
        
    if len(words) <= 2:
        return q in {"more", "next", "continue", "أكثر", "أكمل"}
        
    if words[0] in _NEW_TOPIC_STARTERS and len(words) >= 3:
        return False
        
    return False


class MemoryRetriever:
    """
    Assembles memory context (profile, mistakes, history, summaries)
    to personalize RAG answers without containing document chunks.
    """
    def __init__(self) -> None:
        self.store = MemoryStore()

    async def get_profile(self, user_id: str) -> Optional[UserProfile]:
        return await self.store.get_user_profile(user_id)

    async def get_weak_topics(self, user_id: str, limit: int = 5) -> List[WeakTopic]:
        return await self.store.get_weak_topics(user_id=user_id, resolved=False, limit=limit)

    async def get_recent_mistakes(self, user_id: str, topic: Optional[str] = None, limit: int = 5) -> List[MistakePattern]:
        return await self.store.get_mistakes(user_id=user_id, topic=topic, limit=limit)

    async def get_topic_memories(self, user_id: str, topic: Optional[str] = None) -> List[TopicMastery]:
        return await self.store.get_topic_memory(user_id=user_id, topic=topic)

    async def get_memory_context(
        self,
        user_id: str,
        session_id: str,
        source_id: str,
        source_type: str = "document",
        user_query: str = "",
        max_tokens: int = 1200
    ) -> MemoryContext:
        """
        Assembles complete MemoryContext for the current student interaction.
        Must scope all DB operations by user_id and source_id.
        """
        logger.info(f"Retrieving memory context for user {user_id} in session {session_id} (source: {source_id})")
        
        # 1. Fetch user profile
        profile = await self.get_profile(user_id)
        
        # 2. Fetch recent session messages
        recent_chats = await self.store.get_all_session_messages(user_id, session_id)
        # Sort and limit to recent message budget
        recent_chats = sorted(recent_chats, key=lambda x: x.created_at or datetime.min)
        recent_chats = recent_chats[-memory_config.MAX_RECENT_MESSAGES:]
        
        # 3. Retrieve latest session summary
        summary_record = await self.store.get_latest_summary(user_id, session_id)
        session_summary = None
        structured_summary = {}
        if summary_record:
            session_summary = summary_record.get("summary_text")
            structured_summary = summary_record.get("structured_summary") or {}

        # 4. Semantic search for past relevant memory items
        relevant_past = []
        if user_query:
            try:
                relevant_past = await self.store.semantic_search_memories(
                    user_id=user_id,
                    query=user_query,
                    threshold=memory_config.SIMILARITY_THRESHOLD,
                    limit=memory_config.TOP_K_CHATS
                )
            except Exception as e:
                logger.error(f"Semantic memory retrieval failed: {str(e)}")

        # 5. Retrieve student weak topics
        weak_topics = await self.get_weak_topics(user_id, limit=5)
        # Filter weak topics by source_id if present
        if source_id:
            weak_topics = [wt for wt in weak_topics if not wt.source_id or str(wt.source_id) == str(source_id)]

        # 6. Retrieve recent mistake patterns
        # Detect current topic if continuation or if topic is present
        topic_context = None
        if recent_chats:
            topic_context = recent_chats[-1].topic
            
        recent_mistakes = await self.get_recent_mistakes(user_id, topic=topic_context, limit=5)
        # Filter mistakes by source_id if present
        if source_id:
            recent_mistakes = [m for m in recent_mistakes if not m.source_id or str(m.source_id) == str(source_id)]

        # 7. Retrieve topic mastery records
        topic_memories = await self.get_topic_memories(user_id, topic=topic_context)
        # Filter mastery by source_id if present
        if source_id:
            topic_memories = [tm for tm in topic_memories if not tm.source_id or str(tm.source_id) == str(source_id)]

        # Construct context
        return MemoryContext(
            user_profile=profile,
            recent_messages=recent_chats,
            relevant_past=relevant_past,
            topic_memories=topic_memories,
            weak_topics=weak_topics,
            recent_mistakes=recent_mistakes,
            session_summary=session_summary,
            structured_summary=structured_summary
        )
