# Placeholders for future LLM prompt templates
DEFAULT_CHAT_PROMPT_TEMPLATE = """
You are a study assistant. Answer the user question: {query}
Grounded strictly in the following context:
{context}
"""

DEFAULT_SUMMARY_PROMPT_TEMPLATE = """
Generate a comprehensive document-level summary.
Context:
{context}
"""

DEFAULT_QUIZ_PROMPT_TEMPLATE = """
Generate a quiz with {number_of_questions} questions at {difficulty} difficulty.
Context:
{context}
"""
