import time
import httpx
import logging
import json
from typing import AsyncIterator, Optional, Dict, Any, Type
from pydantic import BaseModel
from .base import BaseLLMProvider
from ..exceptions import (
    ProviderException,
    RateLimitException,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidOutputError,
    LLMProviderUnavailableError
)

logger = logging.getLogger(__name__)

class LLMClientFactory:
    """Centralized factory maintaining reusable clients per API profile for connection sharing."""
    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}

    def get_client(self, profile: str) -> httpx.AsyncClient:
        p = profile.lower().strip()
        if p not in self._clients:
            logger.info(f"Creating reusable HTTPX client for LLM profile '{p}'")
            self._clients[p] = httpx.AsyncClient(
                http2=False,  # Disable HTTP2 to prevent connection reset errors
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=10)
            )
        return self._clients[p]

    async def shutdown(self):
        logger.info("Shutting down all reusable LLM profile HTTPX clients...")
        for profile, client in list(self._clients.items()):
            await client.aclose()
        self._clients.clear()

# Process-wide factory singleton
llm_client_factory = LLMClientFactory()


class GroqProvider(BaseLLMProvider):
    """Groq Provider implementing BaseLLMProvider using shared HTTPX clients."""
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
            raise LLMAuthenticationError("API Key is required but was not provided.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Pop profile-specific metadata if passed
        profile = kwargs.pop("profile", "execution_reduce")

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
        client = llm_client_factory.get_client(profile)

        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Request to Groq timed out: {exc}")
        except httpx.RequestError as exc:
            raise LLMProviderUnavailableError(f"HTTP Request to Groq failed: {exc}")

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if response.status_code == 401:
            raise LLMAuthenticationError(f"Groq authentication failed: {response.text}")
        elif response.status_code == 429:
            raise LLMRateLimitError(f"Groq rate limit exceeded: {response.text}")
        elif response.status_code != 200:
            raise LLMProviderUnavailableError(f"Error from Groq (status {response.status_code}): {response.text}")

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        except (KeyError, ValueError) as exc:
            raise LLMInvalidOutputError(f"Failed to parse Groq response: {exc}")

        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms
        }

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
        res = await self.generate(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            api_key=api_key,
            **kwargs
        )
        try:
            return response_model.model_validate_json(res["text"])
        except Exception as e:
            try:
                import json
                parsed = json.loads(res["text"])
                if isinstance(parsed, dict) and len(parsed) == 1:
                    inner_key = list(parsed.keys())[0]
                    inner_val = parsed[inner_key]
                    if isinstance(inner_val, dict):
                        return response_model.model_validate(inner_val)
            except Exception:
                pass
            raise LLMInvalidOutputError(f"Failed to validate response against Pydantic schema: {e}. Output: {res['text']}")

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
            raise LLMAuthenticationError("API Key is required but was not provided.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        profile = kwargs.pop("profile", "execution_reduce")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        client = llm_client_factory.get_client(profile)
        
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code == 401:
                    raise LLMAuthenticationError("Groq stream authentication failed")
                elif response.status_code == 429:
                    raise LLMRateLimitError("Groq stream rate limit exceeded")
                elif response.status_code != 200:
                    body = await response.aread()
                    raise LLMProviderUnavailableError(f"Streaming error from Groq: {body.decode()}")

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
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Groq stream request timed out: {exc}")
        except httpx.RequestError as exc:
            raise LLMProviderUnavailableError(f"Groq stream connection failed: {exc}")

    def count_tokens(self, text: str, model: str) -> int:
        """Token count estimation supporting Arabic text."""
        if not text:
            return 0
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F')
        is_arabic = (arabic_chars / len(text)) > 0.25 if len(text) > 0 else False
        ratio = 2.0 if is_arabic else 4.0
        return max(1, int(len(text) / ratio))
