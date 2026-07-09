Folder: backend/app/api/

Description:
This folder contains all REST API route definitions and endpoint handlers.
It exposes the system's capabilities to external clients such as front-end apps,
mobile clients, or third-party integrations via versioned HTTP endpoints.

Responsibilities:
- Define and register API routers per version (e.g., v1/)
- Handle HTTP request parsing, validation, and response formatting
- Delegate business logic to AI services or database layers
- Manage API-level authentication and authorization guards

Integration:
Routers defined here are mounted in app/. Requests flow from route handlers
into the AI system or DB layer. Schemas from app/schemas/ are used for
request/response validation via Pydantic models.
