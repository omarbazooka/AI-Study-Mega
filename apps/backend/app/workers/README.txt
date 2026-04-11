Folder: backend/app/workers/

Description:
This folder contains background worker and task queue definitions.
Workers handle long-running, asynchronous, or scheduled tasks that
should not block the main API request-response cycle.

Responsibilities:
- Process document ingestion jobs asynchronously
- Handle reindexing, embedding generation, and batch operations
- Execute scheduled maintenance tasks (cache cleanup, index refresh)
- Manage retry logic and dead-letter queue handling

Integration:
Workers are triggered by the API layer or internal events and delegate
execution to AI services (ingestion/, embeddings/) and the database layer (app/db/).
Typically powered by Celery, ARQ, or a similar async task queue connected
to a Redis or RabbitMQ broker.
