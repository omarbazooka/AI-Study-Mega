Folder: backend/tests/integration/

Description:
This folder contains integration tests that verify the interaction between
multiple system components working together. These tests exercise full
request-response cycles and test real service integrations.

Responsibilities:
- Test API endpoint behavior with a live test database and mocked external APIs
- Verify that AI pipelines correctly chain services end to end
- Test authentication, authorization, and middleware behavior
- Ensure database operations work correctly through the ORM layer

Integration:
Uses a dedicated test database and test client (e.g., FastAPI TestClient or
httpx AsyncClient). External LLM and vector store calls are either mocked
or directed to sandbox environments. Run after unit tests in the CI pipeline.
