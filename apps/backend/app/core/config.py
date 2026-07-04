import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application configuration settings.
    Loads environment variables from OS or .env file.
    """
    # Supabase configurations
    SUPABASE_URL: str = "http://localhost:54321"  # Default URL for local Supabase development
    SUPABASE_SERVICE_ROLE_KEY: str = ""           # Preferred backend-only service_role key
    SUPABASE_KEY: str = ""                        # Fallback key (e.g. anon key or alternate role key)
    SUPABASE_STORAGE_BUCKET: str = "study-documents"

    # Validation limits
    MAX_UPLOAD_SIZE_MB: int = 10


    # Embedding configurations
    # Note: "all-MiniLM-L6-v2" produces 384-dimensional vectors.
    # If this model name is changed, the vector dimension in the migration script
    # and pgvector column must be updated to match the new model's output size.
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
