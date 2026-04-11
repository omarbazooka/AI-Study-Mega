Folder: backend/app/main/

Description:
This folder contains the main application factory and ASGI entry point
for the backend server. It is where the FastAPI (or equivalent) application
instance is created, configured, and exported for the server to run.

Responsibilities:
- Instantiate and configure the ASGI application object
- Register all API routers, middleware, and exception handlers
- Define startup and shutdown lifecycle event hooks
- Initialize database connections, vector store clients, and AI services

Integration:
This is the top-level integration point for the entire backend. It imports
from app/api/ for routers, app/core/ for configuration and middleware,
app/db/ for database initialization, and app/workers/ for task queue setup.
The resulting app object is served by Uvicorn or Gunicorn in production.
