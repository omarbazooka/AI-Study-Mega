Folder: backend/app/ai_system/utils/

Description:
This folder provides shared utility functions and helper classes used
across the AI system modules. It avoids code duplication by centralizing
reusable, stateless logic that does not belong to any single service.

Responsibilities:
- Provide text processing helpers (cleaning, tokenization, truncation)
- Implement retry decorators, async helpers, and rate limit handlers
- Offer formatting utilities for LLM inputs and structured outputs
- Supply logging helpers and performance timing wrappers

Integration:
Imported by any module within ai_system/ that requires shared logic.
Utils are strictly stateless and have no dependencies on other ai_system
components, making them safe to import without circular dependency risk.

