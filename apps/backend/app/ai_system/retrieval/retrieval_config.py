import os
from dataclasses import dataclass


def bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "8"))
    candidate_k: int = int(os.getenv("RETRIEVAL_CANDIDATE_K", "30"))
    similarity_threshold: float = float(os.getenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.20"))
    vector_weight: float = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.65"))
    keyword_weight: float = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.25"))
    metadata_weight: float = float(os.getenv("HYBRID_METADATA_WEIGHT", "0.10"))
    max_context_tokens: int = int(os.getenv("RETRIEVAL_MAX_CONTEXT_TOKENS", "4500"))
    enable_query_rewrite: bool = bool_env("ENABLE_QUERY_REWRITE", True)
    enable_reranker: bool = bool_env("ENABLE_RERANKER", True)
    enable_neighbor_chunks: bool = bool_env("ENABLE_NEIGHBOR_CHUNKS", True)

    def bounded_top_k(self, value):
        return max(1, min(int(value or self.top_k), self.candidate_k))

    def bounded_context_tokens(self, value):
        return max(256, min(int(value or self.max_context_tokens), self.max_context_tokens))


DEFAULT_RETRIEVAL_CONFIG = RetrievalConfig()
