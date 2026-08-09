import time
import httpx
import logging
import json
import re
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
                http2=False,
                timeout=httpx.Timeout(45.0, connect=10.0),
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=10)
            )
        return self._clients[p]

    async def shutdown(self):
        logger.info("Shutting down all reusable LLM profile HTTPX clients...")
        for profile, client in list(self._clients.items()):
            await client.aclose()
        self._clients.clear()


llm_client_factory = LLMClientFactory()


class GroqProvider(BaseLLMProvider):
    """
    Groq provider with a production Cloudflare Workers AI failover.

    Groq remains the preferred provider when its key is healthy. If the key is
    missing/expired, a circuit breaker is open, or Groq is unavailable/rate
    limited, generation transparently falls back to Cloudflare Workers AI using
    the same account/token already used by the embedding pipeline.
    """

    CLOUDFLARE_FALLBACK_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

    def __init__(self, base_url: str = "https://api.groq.com/openai/v1"):
        self.base_url = base_url

    async def _cloudflare_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        profile: str = "execution_reduce",
        original_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.core.config import settings

        account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
        api_token = settings.CLOUDFLARE_API_TOKEN.strip()
        if not account_id or not api_token:
            suffix = f" Original Groq error: {original_error}" if original_error else ""
            raise LLMProviderUnavailableError(
                "Cloudflare LLM fallback is not configured (missing account ID or API token)." + suffix
            )

        model = getattr(settings, "CLOUDFLARE_LLM_MODEL", "").strip() or self.CLOUDFLARE_FALLBACK_MODEL
        base = settings.CLOUDFLARE_AI_BASE_URL.rstrip("/")
        url = f"{base}/accounts/{account_id}/ai/run/{model}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if json_mode:
            messages.append({
                "role": "system",
                "content": "Return only valid JSON. Do not wrap the JSON in markdown code fences or add commentary."
            })
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        client = llm_client_factory.get_client(f"cloudflare_{profile}")
        start_time = time.perf_counter()

        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Cloudflare Workers AI fallback timed out: {exc}") from exc
        except Exception as exc:
            raise LLMProviderUnavailableError(
                f"Cloudflare Workers AI fallback request failed: {exc}. Original Groq error: {original_error or 'n/a'}"
            ) from exc

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        if response.status_code != 200:
            raise LLMProviderUnavailableError(
                f"Cloudflare Workers AI fallback failed (status {response.status_code}): {response.text}. "
                f"Original Groq error: {original_error or 'n/a'}"
            )

        try:
            data = response.json()
            if data.get("success") is False:
                raise ValueError(str(data.get("errors") or data))
            result = data.get("result", {})
            text = ""
            if isinstance(result, dict):
                text = result.get("response") or result.get("text") or ""
                if not text and isinstance(result.get("choices"), list) and result["choices"]:
                    text = result["choices"][0].get("message", {}).get("content", "")
            elif isinstance(result, str):
                text = result
            if not text:
                raise ValueError(f"No generated text in Cloudflare response: {data}")
        except Exception as exc:
            if isinstance(exc, LLMProviderUnavailableError):
                raise
            raise LLMInvalidOutputError(f"Failed to parse Cloudflare Workers AI response: {exc}") from exc

        logger.warning(
            "Groq generation failed; served request through Cloudflare Workers AI fallback model %s. Groq error: %s",
            model,
            original_error or "not configured",
        )
        return {
            "text": text,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": latency_ms,
            "provider": "cloudflare",
            "model": model,
            "fallback_from": "groq",
        }

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
        profile = kwargs.pop("profile", "execution_reduce")

        if not api_key:
            return await self._cloudflare_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                profile=profile,
                original_error="Groq API key is missing",
            )

        from app.ai_system.utils.circuit_breaker import circuit_breaker_registry
        if not await circuit_breaker_registry.allow_request(model):
            return await self._cloudflare_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                profile=profile,
                original_error=f"Groq circuit breaker is open for model '{model}'",
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        from app.core.config import settings
        reasoning_effort = kwargs.pop("reasoning_effort", None)
        include_reasoning = kwargs.pop("include_reasoning", getattr(settings, "GROQ_INCLUDE_REASONING", False))

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

        if model.startswith("openai/gpt-oss"):
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
            payload["include_reasoning"] = include_reasoning
        else:
            payload.pop("reasoning_effort", None)
            payload.pop("include_reasoning", None)

        start_time = time.perf_counter()
        client = llm_client_factory.get_client(profile)

        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                await circuit_breaker_registry.record_success(model)
            else:
                await circuit_breaker_registry.record_failure(model)
        except Exception as exc:
            await circuit_breaker_registry.record_failure(model)
            return await self._cloudflare_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                profile=profile,
                original_error=f"Groq request exception: {exc}",
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if response.status_code != 200:
            return await self._cloudflare_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                profile=profile,
                original_error=f"Groq status {response.status_code}: {response.text}",
            )

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        except (KeyError, ValueError) as exc:
            return await self._cloudflare_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                profile=profile,
                original_error=f"Groq response parsing failed: {exc}",
            )

        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "provider": "groq",
            "model": model,
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
        raw = str(res["text"]).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw).strip()
        try:
            return response_model.model_validate_json(raw)
        except Exception as e:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and len(parsed) == 1:
                    inner_val = next(iter(parsed.values()))
                    if isinstance(inner_val, dict):
                        return response_model.model_validate(inner_val)
                if isinstance(parsed, dict):
                    return response_model.model_validate(parsed)
            except Exception:
                pass
            raise LLMInvalidOutputError(
                f"Failed to validate response against Pydantic schema: {e}. Output: {raw}"
            )

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
        profile = kwargs.pop("profile", "execution_reduce")

        async def cloudflare_fallback(reason: str) -> AsyncIterator[str]:
            result = await self._cloudflare_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=False,
                profile=profile,
                original_error=reason,
            )
            yield result["text"]

        if not api_key:
            async for chunk in cloudflare_fallback("Groq API key is missing"):
                yield chunk
            return

        from app.ai_system.utils.circuit_breaker import circuit_breaker_registry
        if not await circuit_breaker_registry.allow_request(model):
            async for chunk in cloudflare_fallback(f"Groq circuit breaker is open for model '{model}'"):
                yield chunk
            return

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        from app.core.config import settings
        reasoning_effort = kwargs.pop("reasoning_effort", None)
        include_reasoning = kwargs.pop("include_reasoning", getattr(settings, "GROQ_INCLUDE_REASONING", False))

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if model.startswith("openai/gpt-oss"):
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
            payload["include_reasoning"] = include_reasoning
        else:
            payload.pop("reasoning_effort", None)
            payload.pop("include_reasoning", None)

        client = llm_client_factory.get_client(profile)
        fallback_reason: Optional[str] = None

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code == 200:
                    await circuit_breaker_registry.record_success(model)
                else:
                    await circuit_breaker_registry.record_failure(model)
                    body = await response.aread()
                    fallback_reason = f"Groq stream status {response.status_code}: {body.decode(errors='replace')}"

                if response.status_code == 200:
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
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                            except Exception:
                                continue
                    return
        except Exception as exc:
            await circuit_breaker_registry.record_failure(model)
            fallback_reason = f"Groq stream exception: {exc}"

        async for chunk in cloudflare_fallback(fallback_reason or "Groq stream failed"):
            yield chunk

    def count_tokens(self, text: str, model: str) -> int:
        """Token count estimation supporting Arabic text."""
        if not text:
            return 0
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F')
        is_arabic = (arabic_chars / len(text)) > 0.25 if len(text) > 0 else False
        ratio = 2.0 if is_arabic else 4.0
        return max(1, int(len(text) / ratio))
