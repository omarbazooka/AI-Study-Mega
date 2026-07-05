Folder: backend/app/ai-system/validation/

Description:
This folder contains input and output validation logic specific to the AI system.
It ensures that data flowing into and out of agents, pipelines, and LLM calls
meets quality, format, and safety standards before being used or returned.

Responsibilities:
- Validate and sanitize user inputs before processing
- Verify LLM output structure, completeness, and hallucination risk
- Enforce schema compliance on AI-generated responses
- Raise structured errors for invalid or unsafe data

Integration:
Validation is applied at pipeline entry points and after LLM generation.
Works alongside guardrails/ (for policy enforcement) and schemas/ (for data models).
Ensures that context and memory modules only receive clean, well-formed data.
