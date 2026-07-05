Folder: backend/app/ai-system/config/prompts/

Description:
This folder stores all prompt templates used throughout the AI system.
Centralizing prompts here enables consistent, versioned, and easily
maintainable prompt engineering separate from business logic code.

Responsibilities:
- Store system prompts, few-shot examples, and instruction templates
- Organize prompts by use case (RAG answer, summarization, routing, etc.)
- Support template variables for dynamic context injection at runtime
- Enable prompt versioning and A/B testing across pipeline configurations

Integration:
Prompt templates are loaded and rendered by services/llm/ during inference.
The orchestrator and agents reference specific prompt files based on
task type. Prompt changes here directly affect LLM output quality and behavior.
