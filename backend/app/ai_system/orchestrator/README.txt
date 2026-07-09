Folder: backend/app/ai-system/orchestrator/

Description:
This folder contains the central orchestration logic of the AI system.
It is responsible for managing the execution flow of tasks, interpreting user
intents, and coordinating between agents, pipelines, and services.

Responsibilities:
- Parse and classify incoming user intent or task requests
- Route tasks to the appropriate pipeline or agent
- Manage multi-step, sequential, or parallel workflow execution
- Track task state and handle retries or fallbacks

Integration:
Acts as the brain connecting API requests to the AI execution layer.
Works closely with agents/, pipelines/, context/, and memory/ modules.
The orchestrator is typically implemented as a LangGraph state machine or
a custom async task router.
