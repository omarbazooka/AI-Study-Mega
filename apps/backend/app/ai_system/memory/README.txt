Folder: backend/app/ai_system/memory/

Description:
This folder handles persistent and short-term memory for the AI system.
It stores and retrieves conversation history, agent scratchpads, and
long-term user knowledge to enable continuity across sessions.

Responsibilities:
- Persist conversation history per user or session
- Manage short-term in-session memory buffers
- Store and retrieve agent scratchpad state
- Support long-term memory via vector or key-value storage

Integration:
Memory is read at the start of each request to reconstruct session context
and written at the end to persist relevant information. It connects with
ai_system/context/ for runtime enrichment, and with app/db/ for durable storage.
Agents and pipelines read from memory via the context module.

