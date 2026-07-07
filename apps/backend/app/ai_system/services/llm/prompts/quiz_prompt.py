QUIZ_PROMPT_TEMPLATE = """Generate a high-quality educational quiz based on the provided document context.

### Rules:
1. Generate a total of {num_questions} questions.
2. The quiz difficulty should be: {difficulty} (easy, medium, hard).
3. Questions must be strictly based on the context. Do not use external facts.
4. Provide the output in a strict JSON format matching the schema provided. Do not include markdown codeblocks or any text other than the JSON object.
5. If context is insufficient to create a quiz of this size, generate fewer questions or return an empty list in the JSON.
6. The language of the questions and explanations must be Arabic.

### Context:
{context}

### Expected JSON Schema:
{{
  "quiz_title": "string",
  "difficulty": "easy | medium | hard",
  "questions": [
    {{
      "question": "string",
      "type": "mcq",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "Detailed educational explanation pointing back to the context",
      "source_chunk_ids": ["string"]
    }}
  ]
}}

### Strict JSON Output:
"""
