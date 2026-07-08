from .schemas import LLMEngineerPayload, LLMResponsePayload
from .generation_service import GenerationService

async def generate(payload: LLMEngineerPayload) -> LLMResponsePayload:
    """
    Required public integration endpoint for the LLM layer.
    Delegates task execution to GenerationService.
    """
    service = GenerationService()
    return await service.execute_task(payload)
