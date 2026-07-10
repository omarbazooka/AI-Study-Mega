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

    # Google Gemini API Key — preserved in case it is used elsewhere
    GEMINI_API_KEY: str = ""

    # Groq configurations - 5 Key Strategy
    GROQ_DEFAULT_API_KEY: str = ""
    GROQ_PLANNING_API_KEY: str = ""
    GROQ_MEMORY_MAP_API_KEY: str = ""
    GROQ_EXECUTION_REDUCE_API_KEY: str = ""
    GROQ_VERIFICATION_API_KEY: str = ""
    GROQ_QUIZ_API_KEY: str = ""

    # Global default model
    GROQ_DEFAULT_MODEL: str = "llama-3.1-8b-instant"

    # Profile default models
    GROQ_PLANNING_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MEMORY_MAP_MODEL: str = "llama-3.1-8b-instant"
    GROQ_EXECUTION_REDUCE_MODEL: str = "llama-3.1-8b-instant"  # Temporarily switched: llama-3.3-70b-versatile hit daily TPD limit
    GROQ_VERIFICATION_MODEL: str = "llama-3.1-8b-instant"
    GROQ_QUIZ_MODEL: str = "llama-3.1-8b-instant"  # Temporarily switched: llama-3.3-70b-versatile hit daily TPD limit

    # Optional role overrides
    GROQ_PLANNER_MODEL: str = ""
    GROQ_QUERY_REWRITER_MODEL: str = ""
    GROQ_MEMORY_MODEL: str = ""
    GROQ_MAP_MODEL: str = ""
    GROQ_EXECUTOR_MODEL: str = ""
    GROQ_REDUCE_MODEL: str = ""
    GROQ_VERIFIER_MODEL: str = ""
    GROQ_EVALUATOR_MODEL: str = ""
    GROQ_QUIZ_GENERATOR_MODEL: str = ""

    # Embedding configurations
    EMBEDDING_PROVIDER: str = "cloudflare"
    EMBEDDING_MODEL_NAME: str = "@cf/baai/bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32

    # Cloudflare configurations
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_AI_BASE_URL: str = "https://api.cloudflare.com/client/v4"

    # Auth configuration
    AUTH_MODE: str = "supabase"
    MOCK_USER_ID: str = ""
    APP_ENV: str = "development"

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

    def validate_models(self) -> None:
        """Validates that a fallback default model is present."""
        if not self.GROQ_DEFAULT_MODEL.strip():
            raise ValueError("GROQ_DEFAULT_MODEL must not be empty.")

    def validate_auth_settings(self) -> None:
        """Validates the authentication settings."""
        self.AUTH_MODE = self.AUTH_MODE.strip().lower()
        if self.AUTH_MODE not in ("mock", "supabase"):
            raise ValueError(f"Invalid AUTH_MODE: '{self.AUTH_MODE}'. Must be 'mock' or 'supabase'.")

        if self.AUTH_MODE == "mock":
            if self.APP_ENV.strip().lower() == "production":
                raise ValueError("Security Alert: AUTH_MODE cannot be set to 'mock' in production environment.")
            
            if not self.MOCK_USER_ID.strip():
                raise ValueError("MOCK_USER_ID is required when AUTH_MODE is 'mock'.")
            import uuid
            try:
                uuid.UUID(self.MOCK_USER_ID.strip())
            except ValueError:
                raise ValueError(f"MOCK_USER_ID '{self.MOCK_USER_ID}' is not a valid UUID.")

settings = Settings()
settings.validate_models()
settings.validate_auth_settings()

