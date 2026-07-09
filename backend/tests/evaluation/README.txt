Folder: backend/tests/evaluation/

Description:
This folder contains AI-specific evaluation tests that measure the quality
and reliability of RAG pipelines and LLM outputs. Unlike functional tests,
evaluation tests assess semantic correctness and factual accuracy.

Responsibilities:
- Measure RAG metrics: faithfulness, answer relevance, context precision/recall
- Run LLM output benchmarks against a curated golden dataset
- Detect regressions in AI quality after model or prompt changes
- Generate evaluation reports for human review and model selection

Integration:
Uses evaluation frameworks such as RAGAS, DeepEval, or custom scoring scripts.
Tests run against the full AI pipeline (retrieval + generation) with real or
sandboxed LLM calls. Results are stored as reports and monitored over time
to track quality improvements or regressions across releases.
