Folder: backend/app/ai_system/context/

Description:
This folder manages the active runtime context passed between components
during a single AI task or conversation turn. It maintains a structured
view of the current session state used by agents and pipelines.

Responsibilities:
- Build and update the context object per request or session
- Aggregate retrieved documents, user metadata, and chat history
- Provide a unified context interface for agents and LLM calls
- Manage context windowing and token budget constraints

Integration:
Context is populated from retrieval results (services/retrieval/),
user session data (app/db/), and memory (ai_system/memory/).
It is passed into agents and pipelines during execution and is consumed
by the LLM service (services/llm/) during prompt construction.

