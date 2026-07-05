Folder: backend/app/ai-system/services/guardrails/

Description:
This folder implements the safety and policy enforcement layer of the AI system.
Guardrails intercept both incoming user inputs and outgoing LLM responses
to detect and filter harmful, off-topic, or non-compliant content.

Responsibilities:
- Screen user inputs for prompt injection, jailbreaks, and policy violations
- Filter LLM outputs for hallucinations, toxic content, or restricted information
- Apply domain-specific rules (e.g., block medical advice, enforce citation rules)
- Log flagged interactions for audit and compliance review

Integration:
Applied as a pre-processing step before inputs reach the AI pipeline and as a
post-processing step on LLM outputs before they are returned via app/api/.
Works alongside ai-system/validation/ which handles schema and format checks.
