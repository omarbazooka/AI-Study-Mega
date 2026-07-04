Folder: backend/app/ai_system/agents/

Description:
This folder defines all AI agents used in the system.
Each agent is a self-contained autonomous unit capable of reasoning,
using tools, and completing specific subtasks delegated by the orchestrator.

Responsibilities:
- Implement individual agent logic and decision loops
- Define agent-specific tool usage and reasoning strategies
- Expose agent nodes (in nodes/) for graph-based orchestration
- Handle agent-level error recovery and output formatting

Integration:
Agents are invoked by the orchestrator and may call services (LLM, retrieval,
tools) from ai_system/services/. The nodes/ subfolder contains atomic graph
nodes used in LangGraph or similar frameworks for workflow composition.

