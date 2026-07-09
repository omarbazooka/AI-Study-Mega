Folder: backend/app/models/

Description:
This folder contains all ORM database model definitions that map directly
to relational database tables. Models represent the persistent data entities
of the system such as users, documents, sessions, and messages.

Responsibilities:
- Define SQLAlchemy (or equivalent ORM) model classes
- Declare table columns, relationships, and constraints
- Provide model-level methods for common queries or computed properties
- Serve as the single source of truth for the database schema

Integration:
Models are used by app/db/ for session-based CRUD operations and by
app/schemas/ which mirrors them as Pydantic models for API serialization.
Database migrations in app/db/migrations/ are generated from changes to these models.
