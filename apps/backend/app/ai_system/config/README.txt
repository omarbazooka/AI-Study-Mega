Folder: backend/app/ai_system/config/

Description:
This folder stores all static configuration files and constants specific
to the AI system. It centralizes AI-related settings separate from
the application-level configuration in app/core/.

Responsibilities:
- Define AI system constants (model names, chunk sizes, retrieval top-k values)
- Store pipeline and agent configuration dictionaries or YAML/JSON files
- Manage feature flags for experimental AI features
- Provide default fallback values for AI service parameters

Integration:
Read by all AI modules (agents, pipelines, services) at initialization.
Works alongside app/core/ which handles environment variable loading.
The prompts/ subfolder stores all prompt templates consumed by services/llm/.

