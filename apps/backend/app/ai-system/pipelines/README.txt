Folder: backend/app/ai-system/pipelines/

Description:
This folder contains end-to-end AI pipeline definitions.
Each pipeline represents a structured, reusable workflow that chains together
multiple agents, services, and processing steps to accomplish a high-level task.

Responsibilities:
- Define RAG pipelines (ingestion, retrieval, generation)
- Define conversational and task-completion pipelines
- Compose and sequence agents and service calls
- Expose pipeline interfaces consumed by the orchestrator

Integration:
Pipelines are registered in the orchestrator and select the appropriate
services from ai-system/services/. They pull context from ai-system/context/
and persist results via ai-system/memory/ or app/db/.
