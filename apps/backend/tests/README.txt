Folder: backend/tests/

Description:
This folder contains the complete test suite for the backend system.
It is organized into three layers to ensure correctness, integration
integrity, and AI output quality across the full stack.

Responsibilities:
- Provide unit tests for isolated components and utility functions
- Provide integration tests for API endpoints and service interactions
- Provide evaluation tests for AI pipeline quality and LLM output accuracy
- Ensure regressions are caught across all system layers

Subfolders:
- unit/        : Tests for individual functions, classes, and modules in isolation
- integration/ : End-to-end tests covering API routes and service interactions
- evaluation/  : RAG and LLM quality metrics (faithfulness, relevance, accuracy)

Integration:
Tests import from the main app package and use mocked or test-scoped
database and AI service clients. CI/CD pipelines run these tests on every
pull request to protect system stability.
