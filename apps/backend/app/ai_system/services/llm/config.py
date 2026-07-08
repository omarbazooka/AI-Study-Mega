import os
from typing import List

class LLMConfig:
    # Key groups parsed from comma-separated env values
    GROQ_FAST_API_KEYS: List[str] = [
        k.strip() for k in os.getenv("GROQ_FAST_API_KEYS", "").split(",") if k.strip()
    ]
    GROQ_REASONING_API_KEYS: List[str] = [
        k.strip() for k in os.getenv("GROQ_REASONING_API_KEYS", "").split(",") if k.strip()
    ]
    GROQ_SUMMARY_API_KEYS: List[str] = [
        k.strip() for k in os.getenv("GROQ_SUMMARY_API_KEYS", "").split(",") if k.strip()
    ]
    GROQ_VERIFIER_API_KEYS: List[str] = [
        k.strip() for k in os.getenv("GROQ_VERIFIER_API_KEYS", "").split(",") if k.strip()
    ]
    HUGGINGFACE_EMBEDDING_API_KEYS: List[str] = [
        k.strip() for k in os.getenv("HUGGINGFACE_EMBEDDING_API_KEYS", "").split(",") if k.strip()
    ]

    # Default model names for each task class
    DEFAULT_FAST_MODEL: str = os.getenv("DEFAULT_FAST_MODEL", "llama-3.1-8b-instant")
    DEFAULT_REASONING_MODEL: str = os.getenv("DEFAULT_REASONING_MODEL", "llama-3.3-70b-versatile")
    DEFAULT_VERIFIER_MODEL: str = os.getenv("DEFAULT_VERIFIER_MODEL", "llama-3.1-8b-instant")
    DEFAULT_SUMMARY_MODEL: str = os.getenv("DEFAULT_SUMMARY_MODEL", "llama-3.1-8b-instant")

    # Operational settings
    MAX_LLM_RETRIES: int = int(os.getenv("MAX_LLM_RETRIES", "2"))
    API_KEY_COOLDOWN_SECONDS: int = int(os.getenv("API_KEY_COOLDOWN_SECONDS", "60"))

    # Arabic fallback answer
    ARABIC_FALLBACK_ANSWER: str = "لم أجد إجابة واضحة في الملف المرفوع."

    @classmethod
    def get_keys_for_group(cls, group_name: str) -> List[str]:
        group_name = group_name.upper()
        if group_name == "FAST":
            return cls.GROQ_FAST_API_KEYS
        elif group_name == "REASONING":
            return cls.GROQ_REASONING_API_KEYS
        elif group_name == "SUMMARY":
            return cls.GROQ_SUMMARY_API_KEYS
        elif group_name == "VERIFIER":
            return cls.GROQ_VERIFIER_API_KEYS
        elif group_name == "EMBEDDING":
            return cls.HUGGINGFACE_EMBEDDING_API_KEYS
        return []
