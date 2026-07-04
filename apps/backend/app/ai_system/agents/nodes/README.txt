Folder: backend/app/ai_system/agents/nodes/

Description:
This folder contains the individual graph node implementations used to build
agent execution graphs (e.g., LangGraph state machine nodes). Each node
represents a discrete, atomic step in an agent's reasoning or action flow.

Responsibilities:
- Implement callable node functions consumed by the agent graph
- Handle specific subtasks: retrieval, reasoning, tool invocation, summarization
- Accept and return structured graph state objects
- Enable composable, reusable workflow building blocks

Integration:
Nodes are assembled by agent definitions in agents/ into directed graphs.
They call into ai_system/services/ for LLM inference, retrieval, and tool use.
State passed between nodes is enriched by ai_system/context/ and ai_system/memory/.

