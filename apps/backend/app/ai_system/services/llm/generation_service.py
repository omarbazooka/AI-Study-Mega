import logging
from typing import Optional, Any
from .config import LLMConfig
from .exceptions import (
    AllKeysExhaustedException,
    RateLimitException,
    ProviderException,
    JSONParsingException
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

    async def _execute_with_failover(
        self,
        task_type: str,
        model_name: str,
        key_group: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.1,
        fallback_level: int = 0
    ) -> dict:
        """Executes LLM generation with automatic key failover and rate-limit recovery."""
        retries = 0
        max_retries = LLMConfig.MAX_LLM_RETRIES

        fallback_groups = {
            "PLANNING": ("EXECUTION_REDUCE", "GROQ_EXECUTOR_MODEL"),
            "intent_detection": ("EXECUTION_REDUCE", "GROQ_EXECUTOR_MODEL"),
            "FAST": ("REASONING", "GROQ_EXECUTOR_MODEL"),
            "MEMORY_MAP": ("EXECUTION_REDUCE", "GROQ_EXECUTOR_MODEL"),
            "SUMMARY": ("REASONING", "GROQ_EXECUTOR_MODEL"),
            "EXECUTION_REDUCE": ("VERIFICATION", "GROQ_VERIFIER_MODEL"),
            "REASONING": ("VERIFIER", "GROQ_VERIFIER_MODEL"),
            "VERIFICATION": ("PLANNING", "GROQ_PLANNING_MODEL"),
            "VERIFIER": ("FAST", "GROQ_PLANNING_MODEL")
        }

        while retries <= max_retries:
            try:
                # Fetch next active key in pool using round-robin
                key: APIKey = api_key_pool.get_available_key(key_group)
            except AllKeysExhaustedException as e:
                logger.error(f"Failed to execute task key retrieval: {e}")
                if fallback_level < 2 and key_group in fallback_groups:
                    next_group, next_model_env = fallback_groups[key_group]
                    from app.core.config import settings
                    next_model = getattr(settings, next_model_env, "").strip() or settings.GROQ_DEFAULT_MODEL.strip()
                    logger.warning(f"Key group '{key_group}' exhausted. Falling back to role-compatible model tier '{next_group}' using model '{next_model}'...")
                    return await self._execute_with_failover(
                        task_type=task_type,
                        model_name=next_model,
                        key_group=next_group,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        json_mode=json_mode,
                        temperature=temperature,
                        fallback_level=fallback_level + 1
                    )
                raise e

            try:
                logger.info(f"Attempting LLM call using model '{model_name}' and key alias '{key.alias}'...")
                response_data = await self.provider.generate(
                    model=model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    api_key=key.value,
                    profile=key_group.lower()
                )
                
                # Report successful call to clear any cooldowns
                api_key_pool.report_success(key)
                
                # Add key alias metadata to response
                response_data["key_alias"] = key.alias
                return response_data

            except RateLimitException as exc:
                retries += 1
                api_key_pool.report_rate_limit(key)
                logger.warning(f"Rate limit hit on {key.alias}. Retrying with different key ({retries}/{max_retries})...")
                continue
            except ProviderException as exc:
                if exc.status_code and exc.status_code in [400, 401, 403]:
                    # Permanent key error (e.g. invalid key)
                    api_key_pool.disable_key(key)
                else:
                    # Cooldown key temporarily for other provider issues
                    api_key_pool.report_rate_limit(key, cooldown_seconds=10)
                retries += 1
                logger.warning(f"Provider error on {key.alias}: {exc}. Retrying...")
                continue
            except Exception as exc:
                retries += 1
                logger.error(f"Unexpected exception calling provider on key {key.alias}: {exc}")
                continue

        # If we exhausted retries on this group, check fallback to role-compatible model tier
        if fallback_level < 2 and key_group in fallback_groups:
            next_group, next_model_env = fallback_groups[key_group]
            from app.core.config import settings
            next_model = getattr(settings, next_model_env, "").strip() or settings.GROQ_DEFAULT_MODEL.strip()
            logger.warning(f"Retries exhausted for key group '{key_group}'. Falling back to role-compatible model tier '{next_group}' using model '{next_model}'...")
            return await self._execute_with_failover(
                task_type=task_type,
                model_name=next_model,
                key_group=next_group,
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature,
                fallback_level=fallback_level + 1
            )

        raise ProviderException("groq", "Failed to complete LLM execution after key rotation limits reached.")

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

        if task_type == "explain":
            prompt = PromptBuilder.build_explanation_prompt(
                context=context_str,
                topic=payload.task_query or payload.original_user_query
            )
        elif task_type in ["summary", "summary_map"]:
            prompt = PromptBuilder.build_summary_map_prompt(chunks=context_str)
        elif task_type == "summary_reduce":
            prompt = PromptBuilder.build_summary_reduce_prompt(concepts=payload.task_query or payload.original_user_query)
        elif task_type in ["quiz", "quiz_generation"]:
            q_count = payload.expected_llm_output_format.question_count or 5
            diff = (payload.memory_context.quiz_difficulty if payload.memory_context else None) or "medium"
            if diff.startswith("adaptive"):
                diff = diff.split("_")[-1] if "_" in diff else "medium"
            if diff not in ["easy", "medium", "hard"]:
                diff = "medium"
            prompt = PromptBuilder.build_quiz_prompt(context=context_str, num_questions=q_count, difficulty=diff)
            json_mode = True
            schema_model = QuizSchema
        elif task_type == "answer_evaluation":
            q_text = payload.task_query or payload.original_user_query
            expected = ""
            student = ""
            prompt = PromptBuilder.build_evaluation_prompt(
                context=context_str,
                question=q_text,
                expected_answer=expected,
                student_answer=student
            )
            json_mode = True
            schema_model = AnswerEvaluationSchema
        else:
            # Standard chat_answer, chat_simple, comparison_table, key_points, answer_table, etc.
            history = (payload.memory_context.recent_context_summary or "") if payload.memory_context else ""
            prompt = PromptBuilder.build_chat_prompt(
                context=context_str,
                question=payload.task_query or payload.original_user_query,
                history=history
            )


        # 4. Generate LLM Output
        try:
            result = await self._execute_with_failover(
                task_type=task_type,
                model_name=model_name,
                key_group=key_group,
                prompt=prompt,
                json_mode=json_mode
            )
        except Exception as e:
            logger.error(f"Task {task_id} failed LLM execution stage: {e}")
            return LLMResponsePayload(
                task_id=task_id,
                status="failure",
                error_message=str(e)
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
                # Stricter prompt retry
                stricter_prompt = (
                    f"You must return ONLY a valid JSON object matching the schema. Do not include markdown codeblocks or explanations.\n"
                    f"Previous invalid output:\n{text_output}\n"
                    f"Error message: {pe.error_message}\n"
                    f"Please generate the correct JSON block now:"
                )
                try:
                    retry_result = await self._execute_with_failover(
                        task_type=task_type,
                        model_name=model_name,
                        key_group=key_group,
                        prompt=stricter_prompt,
                        json_mode=True
                    )
                    parsed_json_obj = OutputParser.parse_and_validate(retry_result["text"], schema_model)
                    parsed_json = parsed_json_obj.model_dump()
                    
                    # Accumulate token metrics
                    input_tokens += retry_result["input_tokens"]
                    output_tokens += retry_result["output_tokens"]
                    latency_ms += retry_result["latency_ms"]
                    key_alias = retry_result["key_alias"]
                except Exception as retry_exc:
                    logger.error(f"JSON repair failed for task {task_id}: {retry_exc}")
                    token_tracker.log_usage(
                        user_id=user_id,
                        document_id=doc_id,
                        task_type=task_type,
                        provider="groq",
                        model=model_name,
                        key_alias=key_alias,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        status="failure",
                        error_type="JSONParsingException"
                    )
                    return LLMResponsePayload(
                        task_id=task_id,
                        status="failure",
                        error_message=f"JSON validation failed: {pe.error_message}"
                    )

        # 6. Log token usage
        token_tracker.log_usage(
            user_id=user_id,
            document_id=doc_id,
            task_type=task_type,
            provider="groq",
            model=model_name,
            key_alias=key_alias,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            status="success"
        )

        metrics = LLMUsageMetrics(
            provider="groq",
            model=model_name,
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

    async def generate_chat_title(self, first_user_message: str) -> str:
        """Generates a concise, representative title for the chat from the first user message."""
        from .model_router import resolve_config_for_role, LLMRole, ROLE_PROFILE_MAP
        try:
            role = LLMRole.PLANNER
            _, model_name = resolve_config_for_role(role)
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
                "The title should be in the same language as the user's message (e.g. Arabic if the message contains Arabic, English if English). "
                "Keep the title between 2 to 5 words maximum. "
                "Return ONLY the title text, with no quotes, formatting, or extra commentary.\n\n"
                f"User's message:\n{first_user_message}\n\n"
                "Title:"
            )

            result = await self._execute_with_failover(
                task_type="query_rewrite", # uses planning profile
                model_name=model_name,
                key_group=key_group,
                prompt=prompt,
                temperature=0.3
            )
            title = result["text"].strip()
            # Clean up potential surrounding quotes
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1].strip()
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1].strip()
            return title
        except Exception as e:
            logger.error(f"Error in generate_chat_title: {e}")
            return "New Chat"
