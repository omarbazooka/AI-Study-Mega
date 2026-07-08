VERIFIER_PROMPT_TEMPLATE = """Analyze the generated LLM response and determine if it is completely grounded in the provided document context.

### Rules:
1. Ensure the response does not contain any hallucinated facts or general knowledge not present in the context.
2. Check if the response complies with constraints (e.g. returning the fallback phrase if context was missing).
3. If it is grounded, return `True`. If it contains outside knowledge or hallucinations, return `False`.
4. Output only a JSON block with the structure below.

### Context:
{context}

### Generated Response:
{response}

### Expected JSON Output Structure:
{{
  "is_grounded": boolean,
  "reason": "Detailed critique highlighting any unsupported claims (Arabic/English)"
}}

### JSON Output:
"""
