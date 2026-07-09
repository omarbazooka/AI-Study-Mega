You are joining an existing production-oriented AI Study Platform project as the Engineer responsible for Validation / Safety / Verifier.

Your task is NOT to redesign the whole system. Your task is to understand the full project context first, then design and implement only the Validation / Safety layer in a clean, modular, production-ready way that fits the existing architecture.

============================================================
1. PROJECT OVERVIEW
============================================================

The project is an AI-powered educational platform for students. It allows users to upload study materials such as PDFs, then interact with those materials using AI features.

The platform is not a general chatbot. It is a document-bound educational assistant.

Core idea:
- A student uploads a document.
- The backend validates, parses, chunks, embeds, and stores the document.
- The student can ask questions, request explanations, summaries, quizzes, key points, tables, or study support.
- Every AI output must be grounded only in the uploaded document content.
- The system must avoid hallucinations.
- If the answer is not clearly supported by the uploaded document, the system must return:
  "لم أجد إجابة واضحة في الملف المرفوع."

Main AI capabilities:
- Chat with uploaded PDF/document.
- Document-based explanations.
- Structured summaries.
- Quiz generation.
- Flashcards later.
- Study plans later.
- Answer evaluation later.

The MVP is focused on PDF-bound Agentic RAG:
- A document must be uploaded, processed, chunked, embedded, and marked READY before any AI operation.
- The AI must not answer using general world knowledge.
- The AI must only answer using retrieved document context.
- If relevant context is missing, use the fallback message.

============================================================
2. TECH STACK
============================================================

Frontend:
- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

Backend:
- FastAPI
- Python
- Pydantic
- Async background workers

Database / Storage:
- Supabase PostgreSQL
- Supabase Storage
- pgvector
- Row Level Security planned/required

AI Layer:
- LangChain
- LangGraph
- LangSmith for tracing/evaluation later
- Groq LLM APIs during development
- Provider-agnostic LLM design for future OpenAI / Claude / Gemini / other providers
- HuggingFace / Sentence Transformers embeddings, such as BGE models

Current backend folder structure:

NHA-4-094/
│
├── README.md
│
└── apps/
    │
    ├── Frontend/
    │   └── .gitkeep
    │
    └── backend/
        │
        ├── .env
        ├── .env.example
        │
        ├── app/
        │   ├── main.py
        │   │
        │   ├── api/v1/
        │   │   └── documents.py
        │   │
        │   ├── core/
        │   │   └── config.py
        │   │
        │   ├── schemas/
        │   │   └── document_schema.py
        │   │
        │   ├── services/
        │   │   └── document_service.py
        │   │
        │   ├── workers/
        │   │   └── document_worker.py
        │   │
        │   ├── db/
        │   │   ├── supabase_client.py
        │   │   ├── repositories/
        │   │   │   ├── document_repository.py
        │   │   │   └── chunk_repository.py
        │   │   └── migrations/
        │   │       └── 001_init_documents.sql
        │   │
        │   └── ai_system/
        │       ├── ingestion/
        │       │   ├── ingestion_pipeline.py
        │       │   ├── pdf_parser.py
        │       │   ├── cleaner.py
        │       │   ├── chunker.py
        │       │   ├── metadata_generator.py
        │       │   └── document_validator.py
        │       └── providers/
        │           └── embedding_client.py
        │
        ├── scripts/
        ├── tests/
        │   ├── unit/
        │   ├── integration/
        │   └── evaluation/
        └── docker/

============================================================
3. SYSTEM ARCHITECTURE
============================================================

The system follows a layered architecture:

1. Frontend Layer
- Handles user interface.
- File upload.
- Chat interface.
- Summary panel.
- Quiz viewer.
- Displays AI responses, citations, loading states, and errors.

2. API Layer
- FastAPI backend.
- Main endpoints planned/current:
  - /upload_document
  - /chat
  - /summarize
  - /generate_quiz
- Responsible for authentication checks, routing requests, and calling services.

3. Data Ingestion Pipeline
Upload → Validation → Parsing → Cleaning → Structure-aware Chunking → Metadata Generation → Embeddings → Store in Supabase pgvector.

4. Database Layer
- documents table stores file metadata and upload status.
- chunks table stores chunk text, metadata, and vector embeddings.
- chat_sessions/messages tables planned for chat memory and traceability.
- quizzes/questions/attempts planned for assessments.

5. Retrieval Layer
- Hybrid retrieval:
  - vector search
  - keyword search
  - metadata filters
  - reranking later
- Retrieves the most relevant chunks from the uploaded document.

6. Agentic AI Layer
The system uses four main roles:
- Planner: understands user intent and builds execution plan.
- Retriever: retrieves relevant context from pgvector.
- Executor: generates the draft answer, summary, quiz, or explanation.
- Verifier: validates the generated output before returning it.

7. Guardrails / Validation Layer
This is your responsibility.
It checks inputs and outputs, prevents hallucinations, validates formatting, builds citations, calculates confidence scores, and controls fallback/regeneration decisions.

============================================================
4. DAG ORCHESTRATION FLOW
============================================================

The AI chat flow is designed as DAG orchestration.

High-level flow:

Frontend:
User Input
→ Display Response / Ask Clarification / Show Error

Guardrails:
User Input
→ Validate Input
→ Input Valid?
  - Valid → Planner
  - Invalid → Show Error

Planner:
Detect Intent
→ Confidence OK?
  - High confidence → Build DAG Plan
  - Low confidence → Ask Clarification

Orchestrator:
Build DAG Plan
→ Execution Router
→ One of:
  - Single Execution
  - Parallel Execution
  - Sequential Execution
  - Hybrid DAG Execution
→ Launch Pipelines
→ Join Results
→ Handle Partial Failures
→ Merge Responses

Pipeline path 1: Standard RAG for Chat / Explain
Retrieve Memory
→ Rewrite Query
→ Apply Self-Query Filters
→ Hybrid Search
→ Results Found?
  - Found → Select Context Strategy
  - Not found → Expand Search?
      - Yes → Hybrid Search again
      - No → DO NOT use general knowledge. Return insufficient-context fallback.
→ Build Dynamic Prompt
→ Select Model
→ Execute LLM
→ Verify Response

Pipeline path 2: Map-Reduce for Summary / Quiz
Fetch All Chunks
→ Map Phase
→ Reduce Phase
→ Format Output
→ Select Model
→ Execute LLM
→ Verify Response

Final Output:
Join Results
→ Handle Partial Failures
→ Merge Responses
→ Validate Output
→ Build Citations
→ Save Chat State
→ Summarize Memory if needed
→ Display Response

Important correction:
If retrieval fails or context is insufficient, do NOT use general knowledge.
The only allowed fallback is:
"لم أجد إجابة واضحة في الملف المرفوع."

============================================================
5. YOUR ROLE: ENGINEER VALIDATION / SAFETY / VERIFIER
============================================================

You are responsible for the safety and reliability layer.

Your mission:
Prevent hallucinations, validate AI outputs, enforce grounding in retrieved PDF context, build citations, calculate confidence scores, and decide whether the response should be returned, regenerated, retried with more retrieval, or replaced with a fallback.

You are the final quality gate before the response reaches the student.

You must build this as a standalone reusable backend module, not as scattered code inside endpoints.

============================================================
6. WHAT YOU MUST IMPLEMENT
============================================================

Add a new module under:

apps/backend/app/ai_system/validation/

Suggested files:

apps/backend/app/ai_system/validation/
├── __init__.py
├── schemas.py
├── rules.py
├── exceptions.py
├── input_validator.py
├── output_validator.py
├── hallucination_checker.py
├── citation_builder.py
├── confidence.py
├── verifier.py
└── prompts.py

Also add tests:

apps/backend/tests/unit/ai_system/validation/
├── test_input_validator.py
├── test_output_validator.py
├── test_hallucination_checker.py
├── test_citation_builder.py
├── test_confidence.py
└── test_verifier.py

Optional integration tests later:

apps/backend/tests/integration/
└── test_verifier_pipeline.py

============================================================
7. INPUT VALIDATION RESPONSIBILITIES
============================================================

Implement input validation before the Planner runs.

File:
input_validator.py

Responsibilities:
- Sanitize user input.
- Reject empty input.
- Reject extremely long input based on configurable limits.
- Normalize whitespace and invisible characters.
- Detect obvious prompt injection attempts.
- Detect attempts to bypass document grounding.
- Detect attempts to reveal system prompts, API keys, hidden instructions, or internal architecture secrets.
- Ensure document_id/source_id exists in the request.
- Ensure the selected document is READY before AI processing.
- Ensure the request is document-related.
- Ensure the user has permission to access the document.

Some checks will depend on backend/database contracts. For now, implement interfaces and mocks where needed.

Example forbidden intent patterns:
- "ignore previous instructions"
- "use your own knowledge"
- "answer without the document"
- "show system prompt"
- "reveal hidden prompt"
- "give me API key"
- "bypass RAG"
- "pretend the document says"

Important:
Prompt injection detection should not be only regex forever, but regex/rules are acceptable for MVP.

Expected output:
A structured InputValidationResult:
- valid: bool
- sanitized_input: str
- reasons: list[str]
- severity: low | medium | high
- action: continue | reject | ask_clarification

============================================================
8. OUTPUT VALIDATION RESPONSIBILITIES
============================================================

File:
output_validator.py

Validate every output from the Executor before it reaches the user.

General checks:
- Output is not empty.
- Output is not nonsense.
- Output does not contain internal system details.
- Output does not mention unsupported facts.
- Output follows the expected format for the task.
- Output is aligned with the user request.
- Output is grounded in retrieved chunks.
- Output does not use general knowledge.
- Output does not fabricate page numbers, citations, names, definitions, dates, formulas, or examples.

Task-specific checks:

A. Chat / Explanation output:
- Must answer the user question directly.
- Must be supported by retrieved chunks.
- Must not introduce external information.
- If unsupported, fallback.

B. Summary output:
- Must summarize only document content.
- Must not add external concepts.
- Should be structured and readable.
- Should preserve important headings/concepts if available.

C. Quiz output:
- Must be valid JSON or valid Pydantic-compatible structure.
- Each question must have:
  - question text
  - options
  - correct answer
  - explanation
  - citation/source chunk if available
- Correct answer must exist in the options.
- Options must not be duplicated.
- Explanation must be supported by context.
- No unsupported question should be created.

D. Answer evaluation output:
- Must evaluate based on document-grounded expected answer.
- Must provide constructive feedback.
- Must not invent grading criteria not supported by the material unless defined by the system.

Expected output:
OutputValidationResult:
- valid: bool
- reasons: list[str]
- format_errors: list[str]
- safety_errors: list[str]
- action: pass | regenerate | fallback

============================================================
9. HALLUCINATION CHECKING RESPONSIBILITIES
============================================================

File:
hallucination_checker.py

Definition of hallucination in this project:
Any claim in the AI response that is not supported by the retrieved chunks from the uploaded document.

Implement layered hallucination detection:

Layer 1: Rule-based checks
- Detect unsupported numbers.
- Detect unsupported names.
- Detect unsupported dates.
- Detect unsupported definitions.
- Detect forbidden phrases like:
  - "according to my knowledge"
  - "generally speaking"
  - "outside the document"
  - "based on common knowledge"
- Detect if the answer uses concepts not found in context.

Layer 2: Similarity-based checking
- Split answer into claims/sentences.
- Compare each sentence with retrieved chunks.
- Mark claims with low similarity as potentially unsupported.
- Use available embedding client if possible, otherwise implement a simple placeholder interface.

Layer 3: LLM-as-a-Judge
- Use a verification prompt to judge whether the answer is grounded in the context.
- The judge must return structured JSON.
- The judge must not rewrite the answer unless explicitly asked.
- The judge must identify unsupported claims.

Important:
Do not rely only on LLM-as-a-Judge.
Use rules + similarity + LLM judge together.

Expected output:
HallucinationCheckResult:
- grounded: bool
- grounding_score: float
- unsupported_claims: list[str]
- supported_claims: list[str]
- reasons: list[str]
- suggested_action: pass | regenerate | retrieve_more | fallback

============================================================
10. CITATION BUILDER RESPONSIBILITIES
============================================================

File:
citation_builder.py

Build citations that connect the final answer to retrieved chunks.

Input:
- final answer
- retrieved chunks
- chunk metadata

Each chunk should ideally include:
- chunk_id
- text/raw_text
- document_id/source_id
- page_number if available
- section_title if available
- similarity_score if available
- metadata

Output citations:
- chunk_id
- page_number
- section_title
- text_snippet
- relevance_score

Citation rules:
- Do not fabricate citations.
- Do not invent page numbers.
- If page number is missing, citation can use chunk_id and section_title only.
- Every major claim should be traceable to at least one chunk.
- For quizzes, each question/explanation should have a source chunk if possible.
- For summaries, citations can be section-level instead of sentence-level.

Expected output:
CitationBuildResult:
- citations: list[Citation]
- coverage_score: float
- uncited_claims: list[str]

============================================================
11. CONFIDENCE SCORING RESPONSIBILITIES
============================================================

File:
confidence.py

Calculate a confidence score for each AI response.

Suggested formula:
- 40% grounding_score
- 20% citation_coverage
- 15% output_format_score
- 15% context_relevance_score
- 10% llm_judge_score

Confidence labels:
- 0.80–1.00 = high
- 0.60–0.79 = medium
- below 0.60 = low

Rules:
- If confidence < 0.60, do not return the answer directly.
- If confidence is medium, allow only if grounding is acceptable and no serious unsupported claims exist.
- If confidence is high, return answer with citations.

Expected output:
ConfidenceResult:
- score: float
- label: high | medium | low
- factors: dict
- action: return | regenerate | retrieve_more | fallback

============================================================
12. VERIFIER ORCHESTRATOR RESPONSIBILITIES
============================================================

File:
verifier.py

This is the main orchestrator for the validation layer.

It should expose a main function/class method such as:

verify_response(
    user_query,
    task_type,
    retrieved_chunks,
    executor_output,
    plan=None,
    metadata=None
) -> VerificationResult

Verification steps:
1. Validate basic output format.
2. Check grounding against retrieved chunks.
3. Detect unsupported claims.
4. Build citations.
5. Calculate confidence.
6. Decide next action.

Possible actions:
- return
- regenerate
- retrieve_more
- fallback

Decision rules:
- If output is valid, grounded, cited, and confidence is high → return.
- If output has formatting problems but context is enough → regenerate.
- If output is unsupported but retrieval context seems insufficient → retrieve_more.
- If no relevant context exists after retry → fallback.
- If max retries exceeded → fallback.
- If prompt injection or unsafe output detected → fallback or reject.

Final fallback:
"لم أجد إجابة واضحة في الملف المرفوع."

Expected output:
VerificationResult:
- passed: bool
- action: return | regenerate | retrieve_more | fallback
- confidence: float
- reasons: list[str]
- unsupported_claims: list[str]
- citations: list[Citation]
- final_answer: str | None
- metadata: dict

============================================================
13. PROMPTS YOU MUST CREATE
============================================================

File:
prompts.py

Create verification prompts for:

1. Grounding judge prompt
Input:
- user question
- retrieved chunks
- draft answer

Output JSON:
{
  "grounded": true/false,
  "grounding_score": 0.0-1.0,
  "unsupported_claims": [],
  "supported_claims": [],
  "reason": "...",
  "suggested_action": "pass|regenerate|retrieve_more|fallback"
}

2. Quiz validation judge prompt
Input:
- quiz JSON
- retrieved chunks

Output JSON:
{
  "valid": true/false,
  "format_errors": [],
  "unsupported_questions": [],
  "unsupported_explanations": [],
  "suggested_action": "pass|regenerate|fallback"
}

3. Summary validation judge prompt
Input:
- summary
- document chunks

Output JSON:
{
  "valid": true/false,
  "missing_major_topics": [],
  "unsupported_additions": [],
  "suggested_action": "pass|regenerate|fallback"
}

============================================================
14. HOW THIS INTEGRATES WITH LANGGRAPH LATER
============================================================

Your verifier should be usable as a LangGraph node later.

Expected conceptual flow:

def verifier_node(state):
    result = verifier.verify_response(
        user_query=state["user_query"],
        task_type=state["task_type"],
        retrieved_chunks=state["retrieved_chunks"],
        executor_output=state["executor_output"],
        plan=state.get("plan"),
        metadata=state.get("metadata"),
    )

    state["verification"] = result

    if result.action == "return":
        return "final_response"

    if result.action == "regenerate":
        return "executor"

    if result.action == "retrieve_more":
        return "retriever"

    return "fallback"

Do not hard-code LangGraph now unless the project already has it implemented.
Build the verifier as a clean service/module first.

============================================================
15. WHAT CAN BE DONE NOW WITHOUT WAITING FOR OTHER ENGINEERS
============================================================

You can immediately implement:

- validation/schemas.py
- validation/rules.py
- validation/exceptions.py
- input_validator.py
- output_validator.py
- confidence.py
- citation_builder.py using mock chunks
- hallucination_checker.py with rule-based checks first
- prompts.py
- verifier.py with mock integration
- unit tests for all of the above
- mock data for retrieved chunks and executor outputs

Use temporary mock contracts until Planner/Retriever/Executor are ready.

============================================================
16. WHAT YOU MUST WAIT FOR OR MOCK TEMPORARILY
============================================================

You should not block your work, but these contracts will be needed later:

1. Planner / Orchestrator contract:
- shape of the DAG plan
- state keys
- retry count handling
- task_type naming

2. Retriever contract:
- retrieved chunk schema
- similarity score field
- metadata fields
- page number / section title availability

3. Executor contract:
- output format for chat
- output format for summary
- output format for quiz
- output format for answer evaluation

4. Backend / DB contract:
- document access checker
- document status checker
- user permission checker

5. LLM provider wrapper:
- unified LLM call interface for LLM-as-a-Judge
- timeout/retry policy
- model routing for verification

Until these are finalized, use Pydantic schemas and mock interfaces.

============================================================
17. IMPORTANT PROJECT RULES
============================================================

Strict rules:
- Do not answer without retrieved document context.
- Do not use general knowledge fallback.
- Do not fabricate citations.
- Do not fabricate page numbers.
- Do not expose system prompts or internal secrets.
- Do not mix documents between users.
- Do not bypass RLS/security assumptions.
- Do not put validation logic directly inside API endpoints.
- Keep validation modular and reusable.
- Use environment variables for thresholds and optional settings.
- Write tests.
- Keep the implementation production-ready but not overengineered.

Fallback rule:
If the answer is not clearly supported by the uploaded document, return:
"لم أجد إجابة واضحة في الملف المرفوع."

============================================================
18. EXPECTED DELIVERABLES
============================================================

Deliver:

1. Folder:
apps/backend/app/ai_system/validation/

2. Files:
- schemas.py
- rules.py
- exceptions.py
- input_validator.py
- output_validator.py
- hallucination_checker.py
- citation_builder.py
- confidence.py
- verifier.py
- prompts.py

3. Tests:
- test_input_validator.py
- test_output_validator.py
- test_hallucination_checker.py
- test_citation_builder.py
- test_confidence.py
- test_verifier.py

4. Mock examples:
- supported answer example
- hallucinated answer example
- invalid quiz JSON example
- insufficient context example
- prompt injection example

5. Documentation:
A short README explaining:
- what the validation module does
- how to call the verifier
- expected input/output schemas
- how it will integrate with LangGraph
- what is mocked temporarily

============================================================
19. IMPLEMENTATION STYLE
============================================================

Use:
- Python
- Pydantic models
- type hints
- clean error handling
- small focused functions
- no duplicated logic
- no hard-coded secrets
- no unnecessary external dependencies unless justified

Prioritize:
1. Correctness
2. Maintainability
3. Security
4. Scalability
5. Testability
6. Performance

Before writing code:
- inspect the existing files
- reuse existing schemas/config patterns
- do not invent database tables unless necessary
- do not modify unrelated modules
- do not break existing upload/ingestion pipeline

Your first implementation should be standalone and mock-friendly.
Then prepare it for future integration with Planner, Retriever, Executor, and LangGraph.