Folder: backend/app/ai-system/services/ingestion/

Description:
This folder handles the document ingestion pipeline — the process of loading,
parsing, cleaning, and chunking raw documents before they are embedded and
stored in the vector store.

Responsibilities:
- Load documents from various sources (PDF, DOCX, web URLs, databases)
- Parse and extract clean text content from different file formats
- Apply chunking strategies (fixed-size, semantic, recursive) for optimal retrieval
- Attach metadata (source, timestamp, document ID) to each chunk

Integration:
Ingestion is typically triggered by background workers (app/workers/) or
directly via API upload endpoints. Processed chunks are passed to the
embeddings/ service for vectorization and then stored via app/db/.
