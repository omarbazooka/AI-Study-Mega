Folder: backend/app/db/

Description:
This folder manages all database interaction logic for the backend system.
It provides a clean abstraction over the persistence layer, including relational
databases, vector stores, and cache backends.

Responsibilities:
- Define database connection setup and session management
- Provide repository or data access objects (DAOs) for all models
- Manage vector store client initialization (e.g., Pinecone, Qdrant, Weaviate)
- Handle schema migrations via the migrations/ subfolder

Integration:
The DB layer is used by the API layer (app/api/) for CRUD operations and by
AI services (ingestion/, retrieval/, memory/) for storing and querying embedded
documents. SQLAlchemy or a similar ORM manages relational data while a vector
store client handles semantic search indexes.
