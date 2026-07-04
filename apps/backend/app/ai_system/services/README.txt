Folder: backend/app/ai_system/services/

Description:
This folder provides all low-level AI service implementations used across
agents, pipelines, and the orchestrator. Each subfolder is a focused,
technology-specific service module with a clear interface.

Responsibilities:
- Provide ingestion, embedding, retrieval, and LLM inference services
- Implement guardrails for safety and output filtering
- Expose reusable tools callable by agents
- Abstract away external API and library dependencies

Subfolders:
- ingestion/   : Document loading, chunking, and preprocessing
- embeddings/  : Text-to-vector embedding generation
- retrieval/   : Semantic and hybrid search over vector stores
- llm/         : LLM client wrappers and prompt execution
- guardrails/  : Input/output safety checks and policy enforcement
- tools/       : Custom tools and function-calling implementations

Integration:
Services are consumed by agents and pipelines. They interface with external
providers (OpenAI, Pinecone, etc.) and internal modules like context/ and memory/.

