class LLMException(Exception):
    """Base exception for all LLM related errors."""
    pass


class ProviderException(LLMException):
    """Exception raised when an LLM provider returns an error."""
    def __init__(self, provider: str, message: str, status_code: int = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"Provider {provider} failed: {message}")


class RateLimitException(ProviderException):
    """Exception raised when an LLM provider rate limits the request (429)."""
    def __init__(self, provider: str, message: str = "Rate limit exceeded"):
        super().__init__(provider, message, status_code=429)


class AllKeysExhaustedException(LLMException):
    """Exception raised when all API keys in the pool are rate-limited / cooled down."""
    def __init__(self, key_group: str):
        super().__init__(f"All API keys in key pool group '{key_group}' are currently cooled down or exhausted.")


class JSONParsingException(LLMException):
    """Exception raised when the LLM output could not be parsed as valid JSON or conform to schema."""
    def __init__(self, raw_output: str, error_message: str):
        self.raw_output = raw_output
        self.error_message = error_message
        super().__init__(f"Failed to parse LLM output as JSON: {error_message}. Raw output: {raw_output[:200]}...")


class VerifierFailedException(LLMException):
    """Exception raised when output fails safety, alignment, or grounding checks."""
    pass


class ContextMissingException(LLMException):
    """Exception raised when no context is found, triggering the Arabic fallback response."""
    def __init__(self, message: str = "لم أجد إجابة واضحة في الملف المرفوع."):
        super().__init__(message)
