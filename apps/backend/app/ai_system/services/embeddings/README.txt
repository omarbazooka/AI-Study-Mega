Folder: backend/app/ai-system/services/embeddings/

Description:
This folder provides the embedding generation service responsible for converting
text chunks and queries into dense vector representations used for semantic search
and similarity matching.

Responsibilities:
- Wrap embedding model clients (OpenAI, HuggingFace, Cohere, etc.)
- Generate embeddings for document chunks during ingestion
- Generate query embeddings at inference time for retrieval
- Support batching, caching, and multi-model configurations

Integration:
Called by the ingestion/ service to embed document chunks before storage,
and by the retrieval/ service to embed user queries at query time.
Embeddings are stored in the vector database managed through app/db/.
