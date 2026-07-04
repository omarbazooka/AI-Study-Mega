Folder: backend/scripts/

Description:
This folder contains standalone operational and maintenance scripts
for the backend system. These are run manually or via CI/CD to perform
tasks outside the scope of the main application server.

Responsibilities:
- Database setup, seeding, and migration execution scripts
- One-off data ingestion and re-indexing scripts
- Environment setup and dependency validation scripts
- Utility scripts for cache clearing, index rebuilding, and health checks

Integration:
Scripts import from the app package and use the same configuration defined
in app/core/. They interact with app/db/ for database operations and may
trigger ai_system/services/ for batch embedding or ingestion workflows.
Designed to be run from the command line with clear argument interfaces.
