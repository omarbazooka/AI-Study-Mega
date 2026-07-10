import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.schemas.ai_schema import ModelTier, OutputFormat

logger = logging.getLogger(__name__)

class ExecutorConnectionError(Exception):
    """Raised when connecting to the LLM backend provider fails."""
    pass

class ExecutorClient(ABC):
    """Abstract Base Class defining the LLM execution contract."""
    
    @abstractmethod
    async def generate_response(
        self, 
        prompt: str, 
        model_tier: ModelTier, 
        output_format: OutputFormat,
        **kwargs: Any
    ) -> str:
        """
        Generates content from the LLM provider based on a prompt, model tier, and format.
        """
        pass

class MockExecutorClient(ExecutorClient):
    """Development mock implementation of LLM generation."""
    
    async def generate_response(
        self, 
        prompt: str, 
        model_tier: ModelTier, 
        output_format: OutputFormat,
        **kwargs: Any
    ) -> str:
        # Check output format and simulate response based on query details
        lang = kwargs.get("language", "ar")
        difficulty = kwargs.get("difficulty", "medium")
        num_questions = kwargs.get("number_of_questions", 5)

        if output_format == OutputFormat.QUIZ_JSON:
            # Generate valid mock structured Quiz JSON
            questions = []
            for i in range(1, num_questions + 1):
                if lang == "ar":
                    questions.append({
                        "id": f"q{i}",
                        "question": f"سؤال محاكاة {i} حول محتوى الملف المرفوع؟",
                        "options": ["الخيار الصحيح (أ)", "الخيار الخاطئ (ب)", "الخيار الخاطئ (ج)"],
                        "correct": "الخيار الصحيح (أ)"
                    })
                else:
                    questions.append({
                        "id": f"q{i}",
                        "question": f"Simulated Question {i} grounded in the context?",
                        "options": ["Correct Option (A)", "Incorrect Option (B)", "Incorrect Option (C)"],
                        "correct": "Correct Option (A)"
                    })
            return json.dumps(questions, ensure_ascii=False)

        elif output_format == OutputFormat.FLASHCARDS_JSON:
            flashcards = []
            for i in range(1, 4):
                if lang == "ar":
                    flashcards.append({
                        "front": f"مفهوم محاكاة {i}",
                        "back": f"شرح المفهوم المحاكى {i} بالتفصيل."
                    })
                else:
                    flashcards.append({
                        "front": f"Concept {i}",
                        "back": f"Detailed definition of simulated concept {i}."
                    })
            return json.dumps(flashcards, ensure_ascii=False)

        elif output_format == OutputFormat.COMPARISON_TABLE_MARKDOWN:
            if lang == "ar":
                return "### جدول مقارنة محاكى\n| الميزة | الفكرة أ | الفكرة ب |\n|---|---|---|\n| الوصف | تفصيل أ | تفصيل ب |"
            else:
                return "### Simulated Comparison\n| Feature | Concept A | Concept B |\n|---|---|---|\n| Description | Details A | Details B |"

        elif output_format == OutputFormat.ANSWER_TABLE_MARKDOWN:
            # Consumed dynamically or outputted as fallback table
            if lang == "ar":
                return "### جدول الإجابات النموذجية\n| السؤال | الإجابة الصحيحة |\n|---|---|\n| سؤال محاكاة 1 | الخيار الصحيح (أ) |"
            else:
                return "### Sample Answers Table\n| Question | Correct Answer |\n|---|---|\n| Simulated Question 1 | Correct Option (A) |"

        elif output_format == OutputFormat.ANSWER_EVALUATION_JSON:
            eval_res = {
                "score": 85,
                "feedback": "إجابة جيدة جداً، مع تغطية معظم النقاط الرئيسية للملف." if lang == "ar" else "Very good answer, covers core points."
            }
            return json.dumps(eval_res, ensure_ascii=False)

        # Standard Text Markdown Fallback
        if lang == "ar":
            return f"مخرجات محاكاة تعليمية للإجراء المطلوب. تم تأسيسها بدقة بناءً على سياق الملف المرفوع."
        else:
            return f"Simulated educational answer output, grounded strictly in the provided document context."

class RealExecutorClient(ExecutorClient):
    """Production LLM execution engine utilizing Groq provider with key rotation."""
    async def generate_response(
        self, 
        prompt: str, 
        model_tier: ModelTier, 
        output_format: OutputFormat,
        **kwargs: Any
    ) -> str:
        f_keys = LLMConfig.fast_keys()
        if not f_keys or any("dummy" in k for k in f_keys):
            logger.info("No keys or dummy keys. Falling back to MockExecutorClient.")
            mock_client = MockExecutorClient()
            return await mock_client.generate_response(prompt, model_tier, output_format, **kwargs)

        from app.ai_system.services.llm.generate import llm_generate
        
        task_type = "chat_simple"
        if model_tier == ModelTier.REASONING:
            task_type = "chat_complex"
        
        if output_format == OutputFormat.QUIZ_JSON:
            task_type = "quiz_generation"
        elif output_format == OutputFormat.ANSWER_EVALUATION_JSON:
            task_type = "answer_evaluation"
            
        res_payload = await llm_generate(
            prompt=prompt,
            task_type=task_type,
            output_format=output_format.value,
            **kwargs
        )
        
        if res_payload.status == "success" and res_payload.output_text:
            return res_payload.output_text
            
        raise ExecutorConnectionError("LLM response generation failed.")

# Singleton production instance
default_executor_client = RealExecutorClient()
