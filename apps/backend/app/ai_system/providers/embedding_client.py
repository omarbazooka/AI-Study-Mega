import time
import requests
import logging
from app.core.config import settings
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    Client for generating embeddings using Cloudflare Workers AI REST API.
    Model: @cf/baai/bge-m3 -> 1024-dimensional vectors.
    All inference runs on Cloudflare's edge servers.
    """

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL_NAME,
        account_id: str = settings.CLOUDFLARE_ACCOUNT_ID,
        api_token: str = settings.CLOUDFLARE_API_TOKEN,
        base_url: str = settings.CLOUDFLARE_AI_BASE_URL,
    ):
        self.model_name = model_name
        self.account_id = account_id
        self.api_token = api_token
        self.base_url = base_url

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of strings using the Cloudflare Workers AI embedding API.
        Sends texts in batches of EMBEDDING_BATCH_SIZE to avoid payload limits.
        Returns a list of float lists matching the input length.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        batch_size = settings.EMBEDDING_BATCH_SIZE

        # Safety check for credentials
        if not self.account_id or not self.api_token:
            # We raise a clean error without exposing credentials
            logger.error("[EMBEDDING] Cloudflare credentials (CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN) are missing!")
            raise ValueError("Cloudflare credentials are not configured in .env file.")

        url = f"{self.base_url.rstrip('/')}/accounts/{self.account_id}/ai/run/{self.model_name}"
        
        # NEVER log the token or dump headers containing Authorization
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {"text": batch}

            # Retry loop with exponential backoff
            max_retries = 3
            backoff_factor = 2
            success = False
            response_data = None

            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(
                        f"[EMBEDDING] Batch {i // batch_size + 1}/{((len(texts)-1)//batch_size)+1} "
                        f"({len(batch)} items). Attempt {attempt}/{max_retries}..."
                    )
                    
                    # Call with a 30 seconds timeout
                    res = requests.post(url, json=payload, headers=headers, timeout=30)

                    if res.status_code == 200:
                        response_data = res.json()
                        if response_data.get("success"):
                            success = True
                            break
                        else:
                            errors = response_data.get("errors", [])
                            # Safe logging of Cloudflare errors
                            logger.error(f"[EMBEDDING] Cloudflare returned success=False: {errors}")
                    else:
                        # Make sure not to print headers or secrets
                        logger.error(
                            f"[EMBEDDING] HTTP {res.status_code} from Cloudflare. Response: {res.text[:300]}"
                        )
                except requests.RequestException as e:
                    logger.error(f"[EMBEDDING] Network error on attempt {attempt}: {str(e)}")

                if attempt < max_retries:
                    sleep_time = backoff_factor ** attempt
                    logger.info(f"[EMBEDDING] Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)

            if not success:
                raise RuntimeError(
                    f"Failed to generate embeddings via Cloudflare Workers AI after {max_retries} attempts."
                )

            # Response structure: {"result": {"data": [[...], [...]]}, "success": true}
            embeddings = response_data.get("result", {}).get("data", [])

            if len(embeddings) != len(batch):
                raise ValueError(
                    f"Cloudflare returned {len(embeddings)} vectors, but we requested {len(batch)}."
                )

            # Validation: Verify that each vector is exactly 1024 dimensions (or EMBEDDING_DIMENSIONS)
            for idx, vec in enumerate(embeddings):
                if len(vec) != settings.EMBEDDING_DIMENSIONS:
                    raise ValueError(
                        f"Invalid vector dimension at index {idx} in batch. "
                        f"Expected {settings.EMBEDDING_DIMENSIONS}, got {len(vec)}."
                    )

            all_embeddings.extend(embeddings)

        return all_embeddings


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


def embed_query(text: str) -> List[float]:
    """
    Embeds a single query string. Used by app.ai_system.retrieval.vector_store.VectorStore
    (EmbeddingClientProtocol), which expects a single-vector-out embed_query(text) call.
    """
    vectors = embed_texts([text])
    return vectors[0] if vectors else [0.0] * settings.EMBEDDING_DIMENSIONS
