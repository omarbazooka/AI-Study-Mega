"""
Generates the expanded pipeline configuration manifest.
Computes SHA-256 hashes of all behavior-affecting code, prompts, dataset, and document-set.
Redacts API keys and records config values (thresholds, model chains, borrowing policies).
"""
import os
import sys
import json
import hashlib
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
sys.path.insert(0, BACKEND)
load_dotenv(os.path.join(BACKEND, ".env"))

from app.core.config import settings

MANIFEST_JSON = os.path.join(BACKEND, "evaluation", "results", "diagnostics", "pipeline_manifest.json")
MANIFEST_MD   = os.path.join(BACKEND, "evaluation", "results", "diagnostics", "pipeline_manifest.md")

FILES_TO_HASH = {
    "pipeline_registry.py": "app/ai_system/orchestrator/pipeline_registry.py",
    "evidence_gate.py": "app/ai_system/validation/evidence_gate.py",
    "rules.py": "app/ai_system/validation/rules.py",
    "schemas.py": "app/ai_system/validation/schemas.py",
    "context_collector.py": "app/ai_system/validation/context_collector.py",
    "verifier.py": "app/ai_system/validation/verifier.py",
    "verifier_client.py": "app/ai_system/orchestrator/verifier_client.py",
    "retriever_main.py": "app/ai_system/retrieval/retriever_main.py",
    "reranker.py": "app/ai_system/retrieval/reranker.py",
    "reranker_adapters.py": "app/ai_system/retrieval/reranker_adapters.py",
    "generation_service.py": "app/ai_system/services/llm/generation_service.py",
    "model_router.py": "app/ai_system/services/llm/model_router.py",
    "api_key_pool.py": "app/ai_system/services/llm/api_key_pool.py",
    "chat_prompt.py": "app/ai_system/services/llm/prompts/chat_prompt.py",
    "evaluation_prompt.py": "app/ai_system/services/llm/prompts/evaluation_prompt.py",
    "explanation_prompt.py": "app/ai_system/services/llm/prompts/explanation_prompt.py",
    "quiz_prompt.py": "app/ai_system/services/llm/prompts/quiz_prompt.py",
    "summary_prompt.py": "app/ai_system/services/llm/prompts/summary_prompt.py",
    "verifier_prompt.py": "app/ai_system/services/llm/prompts/verifier_prompt.py"
}

def get_file_sha256(rel_path):
    abs_path = os.path.join(BACKEND, rel_path)
    if not os.path.exists(abs_path):
        return "NOT_FOUND"
    h = hashlib.sha256()
    with open(abs_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def main():
    file_hashes = {}
    for name, rel_path in FILES_TO_HASH.items():
        file_hashes[name] = get_file_sha256(rel_path)

    # Hash dataset
    dataset_hash = get_file_sha256("evaluation/datasets/golden_dataset.jsonl")
    # Hash document manifest
    doc_manifest_hash = get_file_sha256("evaluation/datasets/document_manifest.json")

    # Read config policies
    from app.ai_system.validation import rules
    fallback_policy_version = getattr(rules, "FALLBACK_POLICY_VERSION", "v1.0 (bilingual rules.py)")
    evidence_policy_version = "v1.1 (multi-stage Jina/Rule-based thresholds)"
    normalization_version   = "v1.1 (Jina saturation at 0.55)"
    retrieval_recovery_version = "v1.2 (3-attempt retriever relaxation: 0.55 -> 0.40 -> 0.25)"

    # Reranker providers and models
    provider_order = settings.RERANKER_PROVIDER_ORDER
    model_chain = {
        "primary_model": settings.GROQ_PRIMARY_MODEL,
        "fallback_model_1": settings.GROQ_FIRST_FALLBACK_MODEL
    }

    # Extract threshold configurations
    thresholds = {
        "jina_evidence_gate": 0.30,
        "rule_based_evidence_gate": 0.20,
        "retriever_attempt_1": 0.55,
        "retriever_attempt_2": 0.40,
        "retriever_attempt_3": 0.25,
        "jina_score_normalization_saturation": 0.55
    }

    borrowing_allowed = os.environ.get("LLM_ALLOW_CROSS_GROUP_KEY_BORROWING", "false").lower() == "true"

    # Compute composite hash of all code and configuration
    composite_payload = {
        "file_hashes": file_hashes,
        "dataset_hash": dataset_hash,
        "doc_manifest_hash": doc_manifest_hash,
        "thresholds": thresholds,
        "borrowing_allowed": borrowing_allowed,
        "provider_order": provider_order,
        "model_chain": model_chain
    }
    
    composite_json = json.dumps(composite_payload, sort_keys=True)
    composite_hash = hashlib.sha256(composite_json.encode("utf-8")).hexdigest()

    manifest = {
        "composite_hash": composite_hash,
        "fallback_policy_version": fallback_policy_version,
        "evidence_policy_version": evidence_policy_version,
        "normalization_version": normalization_version,
        "retrieval_recovery_version": retrieval_recovery_version,
        "provider_order": provider_order,
        "model_chain": model_chain,
        "threshold_values": thresholds,
        "LLM_ALLOW_CROSS_GROUP_KEY_BORROWING": borrowing_allowed,
        "dataset_hash": dataset_hash,
        "document_set_hash": doc_manifest_hash,
        "file_hashes": file_hashes
    }

    # Save to JSON
    os.makedirs(os.path.dirname(MANIFEST_JSON), exist_ok=True)
    with open(MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[MANIFEST] Saved JSON to {MANIFEST_JSON}")

    # Save to Markdown
    with open(MANIFEST_MD, "w", encoding="utf-8") as f:
        f.write("# Expanded Pipeline Configuration Manifest\n\n")
        f.write(f"- **Composite Hash**: `{composite_hash}`\n")
        f.write(f"- **LLM_ALLOW_CROSS_GROUP_KEY_BORROWING**: `{borrowing_allowed}`\n")
        f.write(f"- **Dataset Hash**: `{dataset_hash}`\n")
        f.write(f"- **Document-Set Hash**: `{doc_manifest_hash}`\n\n")
        
        f.write("## Version Policies\n\n")
        f.write(f"- **Fallback Policy Version**: `{fallback_policy_version}`\n")
        f.write(f"- **Evidence Policy Version**: `{evidence_policy_version}`\n")
        f.write(f"- **Normalization Version**: `{normalization_version}`\n")
        f.write(f"- **Retrieval Recovery Version**: `{retrieval_recovery_version}`\n\n")
        
        f.write("## Execution Parameters\n\n")
        f.write("### 1. Active Model Chain\n")
        f.write(f"- **Primary**: `{model_chain['primary_model']}`\n")
        f.write(f"- **First Fallback**: `{model_chain['fallback_model_1']}`\n\n")
        
        f.write("### 2. Reranker Provider Order\n")
        f.write(f"- `{provider_order}`\n\n")
        
        f.write("### 3. Threshold Values\n")
        for k, v in thresholds.items():
            f.write(f"- **{k}**: `{v}`\n")
            
        f.write("\n## Component File Hashes\n\n")
        f.write("| File Name | SHA-256 Hash |\n")
        f.write("|---|---|\n")
        for k, v in file_hashes.items():
            f.write(f"| `{k}` | `{v}` |\n")

    print(f"[MANIFEST] Saved Markdown to {MANIFEST_MD}")

if __name__ == "__main__":
    main()
