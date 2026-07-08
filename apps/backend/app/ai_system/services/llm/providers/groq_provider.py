import time
import httpx
import logging
import json
from typing import AsyncIterator, Optional, Dict, Any
from .base import BaseLLMProvider
from ..exceptions import ProviderException, RateLimitException

logger = logging.getLogger(__name__)

class GroqProvider(BaseLLMProvider):
    """Groq Provider implementing BaseLLMProvider via raw HTTP calls for dependency minimization."""
    def __init__(self, base_url: str = "https://api.groq.com/openai/v1"):
        self.base_url = base_url

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
        if not api_key:
            raise ProviderException("groq", "API Key is required but was not provided.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise ProviderException("groq", f"HTTP Request failed: {exc}")

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if response.status_code == 429:
            raise RateLimitException("groq", response.text)
        elif response.status_code != 200:
            raise ProviderException("groq", f"Error from Groq: {response.text}", status_code=response.status_code)

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        except (KeyError, ValueError) as exc:
            raise ProviderException("groq", f"Failed to parse response: {exc}")

        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms
        }

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
        if not api_key:
            raise ProviderException("groq", "API Key is required but was not provided.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code == 429:
                        raise RateLimitException("groq", "Rate limit exceeded during stream initialization")
                    elif response.status_code != 200:
                        body = await response.aread()
                        raise ProviderException("groq", f"Streaming error: {body.decode()}", status_code=response.status_code)

                    async for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0]["delta"]
                                if "content" in delta:
                                    yield delta["content"]
                            except Exception:
                                continue
            except httpx.RequestError as exc:
                raise ProviderException("groq", f"HTTP Stream Request failed: {exc}")

    def count_tokens(self, text: str, model: str) -> int:
        """Token count estimation supporting Arabic text."""
        if not text:
            return 0
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F')
        is_arabic = (arabic_chars / len(text)) > 0.25 if len(text) > 0 else False
        ratio = 2.0 if is_arabic else 4.0
        return max(1, int(len(text) / ratio))
