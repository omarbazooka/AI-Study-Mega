Folder: backend/app/ai_system/services/llm/

Description:
This folder provides a unified interface to Large Language Model (LLM) providers.
It abstracts away provider-specific APIs and manages prompt construction,
token budgeting, streaming, and response parsing.

Responsibilities:
- Wrap LLM provider clients (OpenAI, Anthropic, Gemini, local models, etc.)
- Construct final prompts by combining system instructions, context, and history
- Handle streaming and non-streaming response modes
- Manage token counting, model selection, and fallback strategies

Integration:
Called by agents and pipelines after context is assembled by ai_system/context/.
Prompts are built using templates from ai_system/config/prompts/.
Outputs flow back to the agent or pipeline for further processing or direct
API response via app/api/.

