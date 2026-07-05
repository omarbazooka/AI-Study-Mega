Folder: backend/app/ai-system/services/retrieval/

Description:
This folder implements the retrieval service that fetches the most relevant
document chunks from the vector store in response to a user query.
It powers the "R" in the RAG (Retrieval-Augmented Generation) pipeline.

Responsibilities:
- Perform semantic (dense) vector similarity searches
- Support hybrid retrieval combining dense and sparse (BM25) search
- Apply metadata filters, relevance thresholds, and re-ranking
- Return ranked, deduplicated chunks with source attribution

Integration:
Queried by pipelines and agents after receiving a user request.
Uses the embeddings/ service to vectorize the query before search.
Retrieved chunks are passed into ai-system/context/ to build the LLM prompt
and are cited in the final response returned via app/api/.
