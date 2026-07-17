import asyncio
import logging
from typing import List, Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from deepeval.models.base_model import DeepEvalBaseLLM
import nest_asyncio

# Apply nest_asyncio to support running async generation inside synchronous framework wrappers
nest_asyncio.apply()

logger = logging.getLogger(__name__)

def detect_json_mode(prompt: str) -> bool:
    """Heuristic to detect if the judge prompt expects a JSON formatted response."""
    lower_prompt = prompt.lower()
    indicators = ["json", "schema", "output format", "return a json", "json object", "json block"]
    return any(ind in lower_prompt for ind in indicators)

class CentralizedRagasLLM(BaseChatModel):
    """
    Custom Langchain ChatModel adapter for RAGAS.
    Routes calls through the project's central GenerationService failover execution.
    """
    model_name: str = ""
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "centralized-ragas-llm"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        system_prompt = None
        user_prompt_parts = []

        for m in messages:
            if m.type == "system":
                system_prompt = m.content
            else:
                user_prompt_parts.append(m.content)

        prompt = "\n".join(user_prompt_parts)
        json_mode = detect_json_mode(prompt)

        # Import centrally to avoid circular dependencies
        from app.ai_system.services.llm.generation_service import GenerationService
        from app.ai_system.services.llm.model_router import ModelRouter

        service = GenerationService()
        routed_config = ModelRouter.route_task("answer_evaluation")
        
        # Override model name if configured
        model_to_use = self.model_name or routed_config.model_name

        import threading
        if not hasattr(self, "_api_lock"):
            if not hasattr(CentralizedRagasLLM, "_global_api_lock"):
                CentralizedRagasLLM._global_api_lock = threading.Lock()
            self._api_lock = CentralizedRagasLLM._global_api_lock

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        with self._api_lock:
            import time
            time.sleep(6)  # Strict serialization delay to prevent Groq rate limits

            # Execute failover caller synchronously
            try:
                coro = service._execute_with_failover(
                    task_type="ragas-judge",
                    model_name=model_to_use,
                    key_group=routed_config.key_group,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=self.temperature,
                    fallback_models=routed_config.fallback_models
                )
                response = loop.run_until_complete(coro)
                text = response.get("text") or response.get("output_text") or ""
                print(f"[RAGAS_ADAPTER_DEBUG] Prompt: {prompt[:100]}... Response text: {text[:100]}...")
            except Exception as ex:
                import traceback
                traceback.print_exc()
                text = ""

        generation = ChatGeneration(message=AIMessage(content=text))
        return ChatResult(generations=[generation])



class DeepEvalCentralizedLLM(DeepEvalBaseLLM):
    """
    Custom DeepEval LLM adapter.
    Routes calls through the project's central GenerationService failover execution.
    """
    def __init__(self, model_name=""):
        self.model_name = model_name

    def load_model(self):
        return self

    def generate(self, prompt: str) -> str:
        json_mode = detect_json_mode(prompt)

        from app.ai_system.services.llm.generation_service import GenerationService
        from app.ai_system.services.llm.model_router import ModelRouter

        service = GenerationService()
        routed_config = ModelRouter.route_task("answer_evaluation")
        model_to_use = self.model_name or routed_config.model_name

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        import threading
        if not hasattr(self, "_api_lock"):
            if not hasattr(DeepEvalCentralizedLLM, "_global_api_lock"):
                DeepEvalCentralizedLLM._global_api_lock = threading.Lock()
            self._api_lock = DeepEvalCentralizedLLM._global_api_lock

        with self._api_lock:
            import time
            time.sleep(6)  # Strict serialization delay to prevent Groq rate limits

            coro = service._execute_with_failover(
                task_type="deepeval-judge",
                model_name=model_to_use,
                key_group=routed_config.key_group,
                prompt=prompt,
                system_prompt=None,
                json_mode=json_mode,
                temperature=0.0,
                fallback_models=routed_config.fallback_models
            )
            response = loop.run_until_complete(coro)
            return response.get("text") or response.get("output_text") or ""

    async def a_generate(self, prompt: str) -> str:
        json_mode = detect_json_mode(prompt)

        from app.ai_system.services.llm.generation_service import GenerationService
        from app.ai_system.services.llm.model_router import ModelRouter

        service = GenerationService()
        routed_config = ModelRouter.route_task("answer_evaluation")
        model_to_use = self.model_name or routed_config.model_name

        if not hasattr(self, "_async_lock"):
            if not hasattr(DeepEvalCentralizedLLM, "_global_async_lock"):
                DeepEvalCentralizedLLM._global_async_lock = asyncio.Lock()
            self._async_lock = DeepEvalCentralizedLLM._global_async_lock

        async with self._async_lock:
            await asyncio.sleep(6)  # Strict serialization delay to prevent Groq rate limits

            response = await service._execute_with_failover(
                task_type="deepeval-judge",
                model_name=model_to_use,
                key_group=routed_config.key_group,
                prompt=prompt,
                system_prompt=None,
                json_mode=json_mode,
                temperature=0.0,
                fallback_models=routed_config.fallback_models
            )
            return response.get("text") or response.get("output_text") or ""

    def get_model_name(self):
        return self.model_name
