from sentence_transformers import SentenceTransformer
from app.core.config import settings
from typing import List

class EmbeddingClient:
    """
    Client for generating embeddings using the SentenceTransformers library.
    It encapsulates the model loading and inference logic.
    """
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        # Loaded model is kept in memory.
        # "all-MiniLM-L6-v2" is a fast, CPU-friendly model that returns 384 dimensions.
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of strings in batches.
        Returns a list of float lists matching the input length.
        """
        if not texts:
            return []
        
        # Generates numpy array, convert each array to list of floats for DB compatibility
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return [vector.tolist() for vector in embeddings]

# Singleton instance setup for lazy loading/reuse
_embedding_client = None

def get_embedding_client() -> EmbeddingClient:
    """
    Returns the singleton EmbeddingClient instance.
    """
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Convenience function to generate embeddings using the default client.
    """
    return get_embedding_client().embed_texts(texts)
