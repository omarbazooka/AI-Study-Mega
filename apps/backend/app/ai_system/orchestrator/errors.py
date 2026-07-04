class OrchestrationError(Exception):
    """Base exception for all orchestration related errors."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class DocumentNotFoundError(OrchestrationError):
    """Raised when the requested document is not found in the repository."""
    pass

class DocumentAccessDeniedError(OrchestrationError):
    """Raised when the document belongs to another user."""
    pass

class DocumentNotReadyError(OrchestrationError):
    """Raised when the document ingestion is not yet complete (status != 'ready')."""
    pass

class PlanningError(OrchestrationError):
    """Raised when parsing or task planning fails validation constraints."""
    pass

class ExecutionError(OrchestrationError):
    """Raised when executing a specific pipeline task fails."""
    pass

class AllTasksFailedError(OrchestrationError):
    """Raised when all planned tasks fail during orchestration execution."""
    pass
