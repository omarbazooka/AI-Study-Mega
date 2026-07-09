Folder: backend/tests/unit/

Description:
This folder contains unit tests for individual, isolated components
of the backend system. Unit tests verify the correctness of single functions,
classes, or modules without relying on external dependencies.

Responsibilities:
- Test utility functions, helper classes, and pure business logic
- Mock all external dependencies (database, LLM APIs, vector stores)
- Ensure edge cases and error handling paths are covered
- Run fast and in isolation without requiring a running server

Integration:
Tests import directly from app/ modules. All external calls are mocked
using pytest fixtures or libraries like unittest.mock. Unit tests are the
first gate in the CI/CD pipeline and must pass before integration tests run.
