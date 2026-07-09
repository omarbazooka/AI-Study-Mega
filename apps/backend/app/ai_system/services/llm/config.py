import os
from typing import List

def _parse_keys(env_var: str) -> List[str]:
    """Parse comma-separated keys from an env var, falling back to GROQ_API_KEY."""
    specific = [k.strip() for k in os.getenv(env_var, "").split(",") if k.strip()]
    if specific:
        return specific
    # Temporary fallback: use the single GROQ_API_KEY for all groups
    fallback = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]
    return fallback

class LLMConfig:
    # Default model names for each task class
    DEFAULT_FAST_MODEL: str       = os.getenv("DEFAULT_FAST_MODEL", "llama-3.1-8b-instant")
    DEFAULT_REASONING_MODEL: str  = os.getenv("DEFAULT_REASONING_MODEL", "llama-3.3-70b-versatile")
    DEFAULT_VERIFIER_MODEL: str   = os.getenv("DEFAULT_VERIFIER_MODEL", "llama-3.1-8b-instant")
    DEFAULT_SUMMARY_MODEL: str    = os.getenv("DEFAULT_SUMMARY_MODEL", "llama-3.1-8b-instant")

    # Operational settings
    MAX_LLM_RETRIES: int = int(os.getenv("MAX_LLM_RETRIES", "2"))
    API_KEY_COOLDOWN_SECONDS: int = int(os.getenv("API_KEY_COOLDOWN_SECONDS", "60"))

    # Arabic fallback answer
    ARABIC_FALLBACK_ANSWER: str = "لم أجد إجابة واضحة في الملف المرفوع."

    # ── Key groups (read at call-time so load_dotenv in main.py takes effect) ──
    @classmethod
    def get_keys_for_group(cls, group_name: str) -> List[str]:
        group_name = group_name.upper()
        if group_name == "FAST":
            return _parse_keys("GROQ_FAST_API_KEYS")
        elif group_name == "REASONING":
            return _parse_keys("GROQ_REASONING_API_KEYS")
        elif group_name == "SUMMARY":
            return _parse_keys("GROQ_SUMMARY_API_KEYS")
        elif group_name == "VERIFIER":
            return _parse_keys("GROQ_VERIFIER_API_KEYS")
        elif group_name == "EMBEDDING":
            return [k.strip() for k in os.getenv("HUGGINGFACE_EMBEDDING_API_KEYS", "").split(",") if k.strip()]
        return []

    # ── Convenience properties (for backward compat, read at call time) ──────
    @classmethod
    def fast_keys(cls)      -> List[str]: return _parse_keys("GROQ_FAST_API_KEYS")
    @classmethod
    def reasoning_keys(cls) -> List[str]: return _parse_keys("GROQ_REASONING_API_KEYS")
    @classmethod
    def summary_keys(cls)   -> List[str]: return _parse_keys("GROQ_SUMMARY_API_KEYS")
    @classmethod
    def verifier_keys(cls)  -> List[str]: return _parse_keys("GROQ_VERIFIER_API_KEYS")

