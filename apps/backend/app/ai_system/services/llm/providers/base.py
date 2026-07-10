from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any, Type
from pydantic import BaseModel

class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM Providers to support provider-agnostic routing."""

    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        api_key: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Executes a single text generation request.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        model: str,
        prompt: str,
        response_model: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs: Any
    ) -> BaseModel:
        """
        Executes text generation and parses/validates output against a Pydantic schema.
        """
        pass

    @abstractmethod
    async def stream(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """
        Streams generated text chunks as they become available.
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int:
        """
        Calculates or estimates the number of tokens in the given text.
        """
        pass
