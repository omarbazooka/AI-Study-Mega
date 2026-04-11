Folder: backend/app/schemas/

Description:
This folder defines all Pydantic schema classes used for data validation,
serialization, and documentation across the API and AI system layers.
Schemas act as the strict data contracts between system components.

Responsibilities:
- Define request and response schemas for all API endpoints
- Provide internal data transfer objects (DTOs) between services
- Enforce type safety, field validation, and default values
- Auto-generate OpenAPI documentation via FastAPI integration

Integration:
Schemas are imported in app/api/ for request parsing and response formatting.
They mirror app/models/ for database entity representation and are also used
in app/ai-system/ to validate inputs and outputs passing between components.
