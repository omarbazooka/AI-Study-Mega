Folder: backend/app/db/migrations/

Description:
This folder contains database migration scripts that manage schema evolution
over time. Migrations ensure that the relational database schema stays in sync
with the ORM models defined in app/models/ across all environments.

Responsibilities:
- Store auto-generated and manually written migration scripts (e.g., Alembic)
- Track migration history and applied revision versions
- Support upgrade and downgrade operations for schema rollback
- Handle data migrations alongside schema changes when required

Integration:
Migrations are generated from changes to app/models/ using a migration tool
such as Alembic. They are applied during deployment via CI/CD pipelines or
management scripts in backend/scripts/. The target database is configured
through app/core/ settings.
