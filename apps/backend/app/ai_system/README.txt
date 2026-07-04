Folder: backend/app/ai_system/

Description:
This is the core intelligence layer of the entire backend platform.
It encapsulates all Agentic AI and Retrieval-Augmented Generation (RAG) logic,
including orchestration, agent execution, pipelines, memory, and LLM services.

Responsibilities:
- Coordinate all AI-driven workflows end to end
- Manage agent lifecycles, tool usage, and pipeline routing
- Provide retrieval, embedding, and LLM inference services
- Enforce safety through guardrails and validation layers

Integration:
Receives requests from the API layer (app/api/) and interacts with the
database layer (app/db/) for persistent storage. Context and memory modules
feed enriched state into agents and pipelines at runtime.

