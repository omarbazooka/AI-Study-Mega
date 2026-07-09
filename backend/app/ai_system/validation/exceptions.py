class ValidationError(Exception):
    """Base class for all validation-related exceptions in the AI system."""
    pass

class InputValidationError(ValidationError):
    """Raised when the user input fails critical safety or formatting checks."""
    pass

class OutputValidationError(ValidationError):
    """Raised when the AI output is fundamentally malformed or fails strict checks."""
    pass

class HallucinationError(ValidationError):
    """Raised when a severe, unrecoverable hallucination is detected."""
    pass

class GroundingError(ValidationError):
    """Raised when the answer completely lacks support from the retrieved context."""
    pass

class LLMJudgeError(ValidationError):
    """Raised when the LLM-as-a-judge API call fails or returns invalid JSON."""
    pass
