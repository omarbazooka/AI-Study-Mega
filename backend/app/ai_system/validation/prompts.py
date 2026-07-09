"""
LLM Judge Prompts — used by hallucination_checker.py (and later output_validator.py)
to ask an LLM to judge the quality of an already-generated answer.

Important: these prompts NEVER ask the model to generate a new answer or
rewrite anything — they only ask it to judge an existing draft and return
structured JSON.
"""


# ============================================================
# 1. Grounding Judge Prompt — for Chat / Explanation answers
# ============================================================

GROUNDING_JUDGE_PROMPT_TEMPLATE = """You are a strict grounding verifier for an educational AI system.
Your ONLY job is to check whether the DRAFT ANSWER is fully supported by the RETRIEVED CONTEXT.
You must NOT use any outside knowledge. You must NOT rewrite or improve the answer.

USER QUESTION:
{user_question}

RETRIEVED CONTEXT (chunks from the uploaded document):
{retrieved_chunks}

DRAFT ANSWER:
{draft_answer}

Instructions:
- Mark the answer as grounded ONLY if every factual claim in it can be traced to the retrieved context.
- List any claim that is NOT supported by the context as an unsupported claim.
- List the claims that ARE clearly supported as supported claims.
- grounding_score must be a float between 0.0 and 1.0 reflecting the proportion of the answer that is grounded.
- suggested_action must be one of: "pass", "regenerate", "retrieve_more", "fallback".
  - Use "pass" if fully grounded.
  - Use "regenerate" if partially grounded but the context is sufficient to fix it.
  - Use "retrieve_more" if the context seems incomplete for the question.
  - Use "fallback" if the context has nothing relevant to the question.

Respond with ONLY valid JSON, no extra text, no markdown code fences, in exactly this shape:
{{
  "grounded": true/false,
  "grounding_score": 0.0-1.0,
  "unsupported_claims": [],
  "supported_claims": [],
  "reason": "...",
  "suggested_action": "pass|regenerate|retrieve_more|fallback"
}}
"""


def build_grounding_judge_prompt(user_question: str, retrieved_chunks: str, draft_answer: str) -> str:
    """Builds the final grounding-judge prompt text."""
    return GROUNDING_JUDGE_PROMPT_TEMPLATE.format(
        user_question=user_question,
        retrieved_chunks=retrieved_chunks,
        draft_answer=draft_answer,
    )


# ============================================================
# 2. Quiz Validation Judge Prompt
# ============================================================

QUIZ_JUDGE_PROMPT_TEMPLATE = """You are a strict quiz validator for an educational AI system.
Your job is to check whether the QUIZ JSON below is well-formed AND grounded in the DOCUMENT CHUNKS.
You must NOT use any outside knowledge. You must NOT generate new questions or rewrite existing ones.

DOCUMENT CHUNKS (retrieved context):
{retrieved_chunks}

QUIZ JSON:
{quiz_json}

Instructions:
- Check that every question has: question text, options, a correct answer that exists in the options,
  no duplicated options, and an explanation.
- Flag any question whose content (question text, correct answer, or explanation) is NOT supported
  by the document chunks as an unsupported question.
- Flag any explanation whose reasoning is NOT supported by the document chunks as an unsupported explanation.
- suggested_action must be one of: "pass", "regenerate", "fallback".
  - Use "pass" if the quiz is valid and fully grounded.
  - Use "regenerate" if there are fixable format or grounding issues.
  - Use "fallback" if the document chunks don't support generating any valid quiz question.

Respond with ONLY valid JSON, no extra text, no markdown code fences, in exactly this shape:
{{
  "valid": true/false,
  "format_errors": [],
  "unsupported_questions": [],
  "unsupported_explanations": [],
  "suggested_action": "pass|regenerate|fallback"
}}
"""


def build_quiz_judge_prompt(retrieved_chunks: str, quiz_json: str) -> str:
    """Builds the final quiz-judge prompt text."""
    return QUIZ_JUDGE_PROMPT_TEMPLATE.format(
        retrieved_chunks=retrieved_chunks,
        quiz_json=quiz_json,
    )


# ============================================================
# 3. Summary Validation Judge Prompt
# ============================================================

SUMMARY_JUDGE_PROMPT_TEMPLATE = """You are a strict summary validator for an educational AI system.
Your job is to check whether the SUMMARY below is grounded in the DOCUMENT CHUNKS and reasonably complete.
You must NOT use any outside knowledge. You must NOT rewrite the summary.

DOCUMENT CHUNKS (retrieved context):
{document_chunks}

SUMMARY:
{summary}

Instructions:
- Flag any major topic present in the document chunks but missing from the summary as a missing major topic.
- Flag any concept, fact, or claim in the summary that is NOT supported by the document chunks
  as an unsupported addition.
- suggested_action must be one of: "pass", "regenerate", "fallback".
  - Use "pass" if the summary is grounded and reasonably complete.
  - Use "regenerate" if there are fixable gaps or unsupported additions.
  - Use "fallback" if the document chunks don't support producing any meaningful summary.

Respond with ONLY valid JSON, no extra text, no markdown code fences, in exactly this shape:
{{
  "valid": true/false,
  "missing_major_topics": [],
  "unsupported_additions": [],
  "suggested_action": "pass|regenerate|fallback"
}}
"""


def build_summary_judge_prompt(document_chunks: str, summary: str) -> str:
    """Builds the final summary-judge prompt text."""
    return SUMMARY_JUDGE_PROMPT_TEMPLATE.format(
        document_chunks=document_chunks,
        summary=summary,
    )