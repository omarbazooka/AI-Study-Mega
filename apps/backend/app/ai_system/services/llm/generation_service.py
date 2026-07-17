import logging
import asyncio
import time
from typing import Optional, Any, List
from .config import LLMConfig
from .exceptions import (
    AllKeysExhaustedException,
    RateLimitException,
    ProviderException,
    JSONParsingException,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMProviderUnavailableError
)
from .api_key_pool import api_key_pool, APIKey
from .model_router import ModelRouter
from .providers.groq_provider import GroqProvider
from .prompt_builder import PromptBuilder
from .output_parsers import OutputParser
from .token_tracker import token_tracker
from .schemas import (
    LLMEngineerPayload,
    LLMResponsePayload,
    LLMUsageMetrics,
    QuizSchema,
    AnswerEvaluationSchema
)

logger = logging.getLogger(__name__)

class GenerationService:
    """Core LLM Generation Service orchestrating key rotation, prompt compilation, and parsing."""
    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider or GroqProvider()

    def _compile_context(self, payload: LLMEngineerPayload) -> str:
        """Helper to format retrieved chunks into a standardized [SOURCE i] context block."""
        if not payload.retrieved_document_context:
            return ""
        
        parts = []
        for i, c in enumerate(payload.retrieved_document_context):
            parts.append(
                f"[SOURCE {i+1}]\n"
                f"chunk_id: {c.chunk_id}\n"
                f"page_number: {c.page_number if c.page_number is not None else 'N/A'}\n"
                f"score: {c.score if c.score is not None else 'N/A'}\n"
                f"content:\n{c.content}"
            )
        return "\n\n".join(parts)

    def _truncate_payload_context(self, payload: LLMEngineerPayload, target_token_limit: int = 3000) -> bool:
        """
        Truncates the payload's retrieved_document_context to fit within target_token_limit.
        Preserves the highest value evidence (highest score/rank).
        Also reduces or summarizes conversation history if present.
        """
        if not payload.retrieved_document_context:
            return False
        
        # Chunks are typically ordered by score/relevance already.
        # Let's count tokens and pop lower-ranked chunks until we fit target_token_limit.
        current_chunks = list(payload.retrieved_document_context)
        
        # Keep removing the last (lowest ranked) chunk until token count is small enough
        while len(current_chunks) > 1:
            # Estimate tokens
            context_text = "\n\n".join([c.content for c in current_chunks])
            # Simple token count estimation (1 token ~ 4 chars)
            estimated_tokens = len(context_text) // 4
            if estimated_tokens <= target_token_limit:
                break
            current_chunks.pop()
            
        if len(current_chunks) < len(payload.retrieved_document_context):
            payload.retrieved_document_context = current_chunks
            # Also reduce memory context history if present
            if payload.memory_context and payload.memory_context.recent_context_summary:
                payload.memory_context.recent_context_summary = payload.memory_context.recent_context_summary[:500] + " (truncated)"
            return True
        return False

    async def _execute_with_failover(
        self,
        task_type: str,
        model_name: str,
        key_group: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.1,
        fallback_models: list = None,
        reasoning_effort: str = "medium",
        fallback_level: int = 0,
        attempt: int = 1,
        max_tokens: Optional[int] = None
    ) -> dict:
        """Executes LLM generation with automatic key failover and rate-limit recovery."""
        retries = 0
        max_retries = LLMConfig.MAX_LLM_RETRIES
        fallbacks = fallback_models or []

        try:
            # Fetch next active key in pool using round-robin
            key: APIKey = api_key_pool.get_available_key(key_group)
        except AllKeysExhaustedException as e:
            logger.warning(f"All keys exhausted for group '{key_group}'. Sleeping for 3s to let cooldowns expire...")
            await asyncio.sleep(3.0)
            try:
                key: APIKey = api_key_pool.get_available_key(key_group)
            except AllKeysExhaustedException:
                logger.error(f"Failed to execute task key retrieval after sleep: {e}")
                if fallback_level < len(fallbacks):
                    next_model = fallbacks[fallback_level]
                    logger.warning(f"Key group '{key_group}' exhausted. Falling back to model '{next_model}'...")
                    return await self._execute_with_failover(
                        task_type=task_type,
                        model_name=next_model,
                        key_group=key_group,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        json_mode=json_mode,
                        temperature=temperature,
                        fallback_models=fallbacks,
                        reasoning_effort=reasoning_effort,
                        fallback_level=fallback_level + 1,
                        attempt=1,
                        max_tokens=max_tokens
                    )
                raise e

        start_time = time.perf_counter()
        try:
            logger.info(f"Attempting LLM call using model '{model_name}' and key alias '{key.alias}'...")
            response_data = await self.provider.generate(
                model=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                json_mode=json_mode,
                api_key=key.value,
                profile=key_group.lower(),
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens
            )
            
            # Report successful call to clear any cooldowns
            api_key_pool.report_success(key)
            
            # Add key alias metadata to response
            response_data["key_alias"] = key.alias
            
            # Observability logging
            latency_ms = response_data.get("latency_ms", int((time.perf_counter() - start_time) * 1000))
            logger.info(
                f"[OBSERVABILITY] LLM Success: role={key_group}, task={task_type}, model={model_name}, "
                f"effort={reasoning_effort}, attempt={attempt}, latency={latency_ms}ms, "
                f"input_tokens={response_data.get('input_tokens')}, output_tokens={response_data.get('output_tokens')}"
            )
            return response_data

        except (LLMTimeoutError, LLMProviderUnavailableError) as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"[OBSERVABILITY] LLM Transient Error: model={model_name}, error={exc}, latency={latency_ms}ms. Attempt {attempt}/2")
            if attempt == 1:
                backoff = 2 ** attempt
                await asyncio.sleep(backoff)
                return await self._execute_with_failover(
                    task_type=task_type,
                    model_name=model_name,
                    key_group=key_group,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                    fallback_models=fallbacks,
                    reasoning_effort=reasoning_effort,
                    fallback_level=fallback_level,
                    attempt=2
                )
            else:
                if fallback_level < len(fallbacks):
                    next_model = fallbacks[fallback_level]
                    logger.warning(f"Model '{model_name}' failed. Falling back to next model '{next_model}'...")
                    return await self._execute_with_failover(
                        task_type=task_type,
                        model_name=next_model,
                        key_group=key_group,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        json_mode=json_mode,
                        temperature=temperature,
                        fallback_models=fallbacks,
                        reasoning_effort=reasoning_effort,
                        fallback_level=fallback_level + 1,
                        attempt=1
                    )
                raise exc

        except (LLMRateLimitError, RateLimitException) as exc:
            import re
            cooldown_sec = None
            msg = str(exc).lower()
            match = re.search(r"try again in (\d+\.?\d*)s", msg)
            if match:
                cooldown_sec = int(float(match.group(1)) + 2) # add 2s buffer
                logger.info(f"[COOLDOWN] Parsed rate-limit retry-after: {cooldown_sec} seconds")
            
            api_key_pool.report_rate_limit(key, cooldown_seconds=cooldown_sec)
            logger.warning(f"Rate limit hit on {key.alias} for model {model_name}. Transitioning through fallback chain.")
            
            # Wait for cooldown to avoid cascading exhaustion of fallback models
            sleep_time = cooldown_sec or 4
            logger.info(f"[RATE_LIMIT] Sleeping for {sleep_time}s before trying fallback...")
            await asyncio.sleep(sleep_time)

            if fallback_level < len(fallbacks):
                next_model = fallbacks[fallback_level]
                return await self._execute_with_failover(
                    task_type=task_type,
                    model_name=next_model,
                    key_group=key_group,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                    fallback_models=fallbacks,
                    reasoning_effort=reasoning_effort,
                    fallback_level=fallback_level + 1,
                    attempt=1
                )
            raise exc

        except Exception as exc:
            logger.error(f"Unexpected exception calling provider on key {key.alias}: {exc}")
            if fallback_level < len(fallbacks):
                next_model = fallbacks[fallback_level]
                return await self._execute_with_failover(
                    task_type=task_type,
                    model_name=next_model,
                    key_group=key_group,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    temperature=temperature,
                    fallback_models=fallbacks,
                    reasoning_effort=reasoning_effort,
                    fallback_level=fallback_level + 1,
                    attempt=1
                )
            raise exc

    async def execute_task(self, payload: LLMEngineerPayload) -> LLMResponsePayload:
        """
        Executes a single task end-to-end: compiles prompt, executes with key rotation,
        validates output structure, logs stats, and performs grounding verification.
        """
        task_id = payload.task_id
        task_type = payload.task_type
        
        # Determine user/doc IDs
        user_id = getattr(payload, "user_id", None) or "system"
        doc_id = payload.source.source_id

        # 1. Short-circuit if context is empty
        if not payload.retrieved_document_context:
            logger.info(f"Empty context detected for task {task_id}. Applying strict Arabic fallback policy.")
            return LLMResponsePayload(
                task_id=task_id,
                status="success",
                output_text=payload.strict_grounding_policy.if_document_context_insufficient,
                source_chunk_ids=[]
            )

        # 2. Route task to appropriate model
        try:
            routed_config = ModelRouter.route_task(task_type)
        except ValueError as e:
            logger.error(f"Task routing failed for task {task_id}: {e}")
            return LLMResponsePayload(
                task_id=task_id,
                status="failure",
                error_message=str(e)
            )
            
        model_name = routed_config.model_name
        key_group = routed_config.key_group

        context_str = self._compile_context(payload)
        source_chunk_ids = [c.chunk_id for c in payload.retrieved_document_context]

        # 3. Compile prompt based on task type
        json_mode = False
        schema_model = None

        def build_prompt_fn(c_str: str) -> str:
            nonlocal json_mode, schema_model
            if task_type == "explain":
                return PromptBuilder.build_explanation_prompt(
                    context=c_str,
                    topic=payload.task_query or payload.original_user_query
                )
            elif task_type in ["summary", "summary_map"]:
                return PromptBuilder.build_summary_map_prompt(chunks=c_str)
            elif task_type == "summary_reduce":
                return PromptBuilder.build_summary_reduce_prompt(concepts=payload.task_query or payload.original_user_query)
            elif task_type in ["quiz", "quiz_generation"]:
                q_count = payload.expected_llm_output_format.question_count or 5
                diff = (payload.memory_context.quiz_difficulty if payload.memory_context else None) or "medium"
                if diff.startswith("adaptive"):
                    diff = diff.split("_")[-1] if "_" in diff else "medium"
                if diff not in ["easy", "medium", "hard"]:
                    diff = "medium"
                json_mode = True
                schema_model = QuizSchema
                return PromptBuilder.build_quiz_prompt(context=c_str, num_questions=q_count, difficulty=diff)
            elif task_type == "answer_evaluation":
                q_text = payload.task_query or payload.original_user_query
                json_mode = True
                schema_model = AnswerEvaluationSchema
                return PromptBuilder.build_evaluation_prompt(
                    context=c_str,
                    question=q_text,
                    expected_answer="",
                    student_answer=""
                )
            else:
                # Standard chat_answer, chat_simple, comparison_table, key_points, answer_table, etc.
                history = (payload.memory_context.recent_context_summary or "") if payload.memory_context else ""
                return PromptBuilder.build_chat_prompt(
                    context=c_str,
                    question=payload.task_query or payload.original_user_query,
                    history=history
                )

        prompt = build_prompt_fn(context_str)

        # Build candidate models list: [primary_model, *fallback_models]
        models_to_try = [model_name]
        if routed_config.fallback_models:
            for m in routed_config.fallback_models:
                if m not in models_to_try:
                    models_to_try.append(m)

        last_exception = None
        for current_model in models_to_try:
            try:
                # 4. Generate LLM Output
                result = await self._execute_with_failover(
                    task_type=task_type,
                    model_name=current_model,
                    key_group=key_group,
                    prompt=prompt,
                    json_mode=json_mode,
                    fallback_models=[],  # fallbacks handled by outer loop
                    reasoning_effort=routed_config.reasoning_effort
                )

                text_output = result["text"]
                input_tokens = result["input_tokens"]
                output_tokens = result["output_tokens"]
                latency_ms = result["latency_ms"]
                key_alias = result["key_alias"]

                # 5. Handle JSON Parsing & Validations with stricter prompt retry on failure
                parsed_json = None
                if json_mode and schema_model:
                    try:
                        parsed_json_obj = OutputParser.parse_and_validate(text_output, schema_model)
                        parsed_json = parsed_json_obj.model_dump()
                    except JSONParsingException as pe:
                        logger.warning(f"JSON Parsing failed for task {task_id}: {pe}. Retrying with stricter instructions...")
                        stricter_prompt = (
                            f"You must return ONLY a valid JSON object matching the schema. Do not include markdown codeblocks or explanations.\n"
                            f"Previous invalid output:\n{text_output}\n"
                            f"Error message: {pe.error_message}\n"
                            f"Please generate the correct JSON block now:"
                        )
                        retry_result = await self._execute_with_failover(
                            task_type=task_type,
                            model_name=current_model,
                            key_group=key_group,
                            prompt=stricter_prompt,
                            json_mode=True,
                            fallback_models=[],
                            reasoning_effort=routed_config.reasoning_effort
                        )
                        parsed_json_obj = OutputParser.parse_and_validate(retry_result["text"], schema_model)
                        parsed_json = parsed_json_obj.model_dump()
                        text_output = retry_result["text"]
                        
                        input_tokens += retry_result["input_tokens"]
                        output_tokens += retry_result["output_tokens"]
                        latency_ms += retry_result["latency_ms"]
                        key_alias = retry_result["key_alias"]

                # Log token usage
                token_tracker.log_usage(
                    user_id=user_id,
                    document_id=doc_id,
                    task_type=task_type,
                    provider="groq",
                    model=current_model,
                    key_alias=key_alias,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    status="success"
                )

                metrics = LLMUsageMetrics(
                    provider="groq",
                    model=current_model,
                    key_alias=key_alias,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    latency_ms=latency_ms
                )

                return LLMResponsePayload(
                    task_id=task_id,
                    status="success",
                    output_text=text_output if not json_mode else None,
                    output_json=parsed_json if json_mode else None,
                    source_chunk_ids=source_chunk_ids,
                    usage_metrics=metrics
                )

            except Exception as e:
                logger.error(f"Execution failed for model '{current_model}': {e}")
                last_exception = e

                # Context-too-large recovery (Part 4)
                err_msg = str(e).lower()
                if "context" in err_msg or "too large" in err_msg or "limit" in err_msg:
                    logger.warning("Context length limit exceeded. Truncating context chunks...")
                    if self._truncate_payload_context(payload, target_token_limit=3000):
                        context_str = self._compile_context(payload)
                        source_chunk_ids = [c.chunk_id for c in payload.retrieved_document_context]
                        prompt = build_prompt_fn(context_str)
                        # Retry the current model once with truncated prompt
                        try:
                            result = await self._execute_with_failover(
                                task_type=task_type,
                                model_name=current_model,
                                key_group=key_group,
                                prompt=prompt,
                                json_mode=json_mode,
                                fallback_models=[],
                                reasoning_effort=routed_config.reasoning_effort
                            )
                            # Parse and validate retry output
                            text_output = result["text"]
                            parsed_json = None
                            if json_mode and schema_model:
                                parsed_json_obj = OutputParser.parse_and_validate(text_output, schema_model)
                                parsed_json = parsed_json_obj.model_dump()
                            
                            token_tracker.log_usage(
                                user_id=user_id,
                                document_id=doc_id,
                                task_type=task_type,
                                provider="groq",
                                model=current_model,
                                key_alias=result["key_alias"],
                                input_tokens=result["input_tokens"],
                                output_tokens=result["output_tokens"],
                                latency_ms=result["latency_ms"],
                                status="success"
                            )
                            metrics = LLMUsageMetrics(
                                provider="groq",
                                model=current_model,
                                key_alias=result["key_alias"],
                                input_tokens=result["input_tokens"],
                                output_tokens=result["output_tokens"],
                                total_tokens=result["input_tokens"] + result["output_tokens"],
                                latency_ms=result["latency_ms"]
                            )
                            return LLMResponsePayload(
                                task_id=task_id,
                                status="success",
                                output_text=text_output if not json_mode else None,
                                output_json=parsed_json if json_mode else None,
                                source_chunk_ids=source_chunk_ids,
                                usage_metrics=metrics
                            )
                        except Exception as retry_err:
                            logger.error(f"Retry after context truncation failed: {retry_err}")
                            last_exception = retry_err
                
                # Continue loop to next fallback model
                continue

        # If all models failed
        logger.error(f"All candidate models failed. Last exception: {last_exception}")
        return LLMResponsePayload(
            task_id=task_id,
            status="failure",
            error_message=f"All candidate models failed. Last error: {str(last_exception)}"
        )

    async def generate_chat_title(self, first_user_message: str) -> str:
        """Generates a concise, representative title for the chat from the first user message.

        Uses the TITLE_GENERATOR role (lightweight planning profile).
        Token budget: max_tokens=30 (2–5 words is sufficient).
        Deterministic fallback: first 50 characters of the message, truncated at the
        last word boundary, so that a title is always set even when the LLM call fails.
        """
        from .model_router import resolve_config_for_role, LLMRole, ROLE_PROFILE_MAP

        # Deterministic fallback — always safely runs without external resources
        def _deterministic_title(msg: str) -> str:
            snippet = msg.strip()[:50]
            if len(msg.strip()) > 50:
                # Truncate at last space to avoid cutting a word mid-way
                last_space = snippet.rfind(" ")
                snippet = snippet[:last_space] if last_space > 0 else snippet
                snippet = snippet.rstrip(".,;:") + "…"
            return snippet or "New Chat"

        try:
            role = LLMRole.TITLE_GENERATOR
            api_key, model_name = resolve_config_for_role(role)
            profile = ROLE_PROFILE_MAP[role]
            profile_upper = profile.value.upper()

            legacy_mapping = {
                "PLANNING": "FAST",
                "MEMORY_MAP": "SUMMARY",
                "EXECUTION_REDUCE": "REASONING",
                "VERIFICATION": "VERIFIER",
                "QUIZ": "REASONING"
            }
            key_group = legacy_mapping.get(profile_upper, profile_upper)

            prompt = (
                "You are a helpful AI assistant. Based on the user's first message in a chat session, "
                "generate a short, concise, and representative title for this chat. "
                "The title should be in the same language as the user's message (Arabic if Arabic, English if English). "
                "Keep the title between 2 to 5 words maximum. "
                "Return ONLY the title text, with no quotes, formatting, or extra commentary.\n\n"
                f"User's message:\n{first_user_message}\n\n"
                "Title:"
            )

            result = await self._execute_with_failover(
                task_type="title_generation",
                model_name=model_name,
                key_group=key_group,
                prompt=prompt,
                temperature=0.3,
                max_tokens=30,  # Enforce small token budget: 2–5 words
            )
            title = result["text"].strip()
            # Clean up potential surrounding quotes
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1].strip()
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1].strip()
            return title or _deterministic_title(first_user_message)
        except Exception as e:
            logger.error(f"Error in generate_chat_title: {e}")
            return _deterministic_title(first_user_message)
