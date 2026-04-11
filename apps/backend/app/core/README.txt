Folder: backend/app/core/

Description:
This folder holds the foundational configuration and cross-cutting concerns
of the backend application. It provides shared infrastructure that every
other module in the system depends on.

Responsibilities:
- Load and validate environment variables and application settings
- Configure logging, exception handlers, and middleware
- Provide dependency injection utilities and lifespan event hooks
- Define security utilities such as JWT handling and API key validation

Integration:
All modules across the system (api/, ai-system/, db/, workers/) import
from core/ to access settings, logger instances, and shared dependencies.
It is the first layer initialized when the application starts up.
