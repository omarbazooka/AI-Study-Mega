Folder: backend/app/api/v1/

Description:
This folder contains all versioned API route handlers for version 1 of the backend.
Versioning isolates breaking changes and allows backward-compatible evolution
of the public API without disrupting existing clients.

Responsibilities:
- Define routers for all v1 endpoints (chat, documents, sessions, health, etc.)
- Group routes logically by feature (e.g., chat.py, documents.py, users.py)
- Apply v1-specific middleware, dependencies, and auth guards
- Map HTTP requests to the appropriate service or AI pipeline call

Integration:
All routers in this folder are registered in app/api/ and mounted under the /v1 prefix.
They use schemas from app/schemas/ for request/response models and delegate
business logic to app/ai-system/ or app/db/ layers.
