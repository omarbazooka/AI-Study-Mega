Folder: backend/app/

Description:
This is the root application package of the backend system.
It serves as the central entry point that wires together all modules,
including the API layer, AI system, database layer, and background workers.

Responsibilities:
- Register all API routers and middleware
- Initialize core configuration and dependencies
- Bootstrap database connections and vector stores
- Mount the AI system and background task workers

Integration:
All sub-packages (api, ai-system, db, workers) are imported and initialized here.
The main application factory lives in this layer and is consumed by the ASGI server.
