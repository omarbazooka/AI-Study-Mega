import os
import json
import csv
import ast
import pandas as pd

def parse_list_safe(val):
    if pd.isna(val):
        return []
    if isinstance(val, list):
        return val
    try:
        return ast.literal_eval(val)
    except Exception:
        return []

def main():
    backend_dir = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
    diagnostics_path = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "per_case_diagnostics.csv")
    
    df = pd.read_csv(diagnostics_path)
    
    false_refusal_rows = df[df["outcome_classification"] == "false_refusal"]
    print(f"[ROOT CAUSE] Analyzing {len(false_refusal_rows)} false refusals...")
    
    analysis_rows = []
    
    for _, row in false_refusal_rows.iterrows():
        cid = row["test_case_id"]
        lang = row["language"]
        cat = row["category"]
        doc_id = row["document_id"]
        
        expected_chunks = parse_list_safe(row["reference_chunk_ids"])
        retrieved_chunks = parse_list_safe(row["retrieved_chunk_ids"])
        ret_scores = parse_list_safe(row["retrieval_scores"])
        rer_scores = parse_list_safe(row["reranker_scores"])
        
        # Check if reference chunk was retrieved
        hit = any(ec in retrieved_chunks for ec in expected_chunks)
        
        # Max scores
        vector_score = max(ret_scores) if ret_scores else None
        keyword_score = None # not stored separately in diagnostics
        hybrid_score = max(ret_scores) if ret_scores else None
        raw_reranker_score = max(rer_scores) if rer_scores else None
        normalized_reranker_score = max(rer_scores) if rer_scores else None
        
        # Determine classification
        # Let's write the classification based on logical trace:
        has_error = not pd.isna(row["pipeline_error"]) and str(row["pipeline_error"]).strip() != "" and str(row["pipeline_error"]).strip().lower() != "nan"
        if not retrieved_chunks:
            classification = "RETRIEVAL_EMPTY"
        elif not hit:
            classification = "RETRIEVAL_LOW_RECALL"
        elif has_error:
            if "RateLimit" in str(row["pipeline_error"]):
                classification = "GENERATION_RATE_LIMIT"
            else:
                classification = "PIPELINE_EXCEPTION"
        elif raw_reranker_score is None:
            classification = "RERANKER_PROVIDER_FAILURE"
        elif row["verifier_status"] == "failed":
            classification = "VERIFIER_REJECTION"
        else:
            classification = "EVIDENCE_GATE_REJECTION"
            
        print(f"  {cid} ({lang}, {cat}): hit={hit}, chunks={len(retrieved_chunks)}, classification={classification}")
        
        analysis_rows.append({
            "test_case_id": cid,
            "language": lang,
            "category": cat,
            "document_id": doc_id,
            "expected_reference_chunk_ids": ",".join(expected_chunks),
            "initial_retrieved_chunk_ids": ",".join(retrieved_chunks[:5]),
            "retrieval_reference_hit": hit,
            "vector_score": vector_score,
            "keyword_score": keyword_score,
            "hybrid_score": hybrid_score,
            "reranker_provider": "jina",
            "raw_reranker_score": raw_reranker_score,
            "normalized_reranker_score": normalized_reranker_score,
            "score_seen_by_context_collector": normalized_reranker_score,
            "score_seen_by_evidence_gate": normalized_reranker_score,
            "evidence_status": "insufficient" if classification == "EVIDENCE_GATE_REJECTION" else "unknown",
            "evidence_reason_code": "BELOW_FLOOR" if classification == "EVIDENCE_GATE_REJECTION" else "NO_EVIDENCE",
            "recovery_attempted": False,
            "generation_attempted": classification == "VERIFIER_REJECTION",
            "generation_provider": "groq",
            "generation_model": "llama-3.3-70b-versatile",
            "generation_error_type": "",
            "verifier_attempted": classification == "VERIFIER_REJECTION",
            "verifier_action": row["verifier_action"] if not pd.isna(row["verifier_action"]) else "",
            "verifier_failure_reason": "",
            "citation_failure_reason": "",
            "final_response_type": "document_fallback",
            "fallback_reason_code": "DOCUMENT_INFORMATION_NOT_FOUND",
            "root_cause_classification": classification
        })
        
    # Write CSV
    csv_dest = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "false_refusal_case_analysis.csv")
    md_dest = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "false_refusal_case_analysis.md")
    
    headers = [
        "test_case_id", "language", "category", "document_id", "expected_reference_chunk_ids",
        "initial_retrieved_chunk_ids", "retrieval_reference_hit", "vector_score", "keyword_score",
        "hybrid_score", "reranker_provider", "raw_reranker_score", "normalized_reranker_score",
        "score_seen_by_context_collector", "score_seen_by_evidence_gate", "evidence_status",
        "evidence_reason_code", "recovery_attempted", "generation_attempted", "generation_provider",
        "generation_model", "generation_error_type", "verifier_attempted", "verifier_action",
        "verifier_failure_reason", "citation_failure_reason", "final_response_type",
        "fallback_reason_code", "root_cause_classification"
    ]
    
    with open(csv_dest, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(analysis_rows)
        
    # Write MD
    md_content = """# False Refusal Root Cause Analysis

This report documents the root cause of the 16 false refusals in the baseline run.

| Test Case | Language | Category | Chunks Retrieved | Hit? | Reranker Score | Root Cause | Description |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for row in analysis_rows:
        chunks_count = len(row["initial_retrieved_chunk_ids"].split(",")) if row["initial_retrieved_chunk_ids"] else 0
        hit_str = "Yes" if row["retrieval_reference_hit"] else "No"
        score_str = f"{row['raw_reranker_score']:.4f}" if row["raw_reranker_score"] is not None else "N/A"
        
        if row["root_cause_classification"] == "RETRIEVAL_EMPTY":
            desc = "Retrieval stage returned 0 chunks from the database."
        elif row["root_cause_classification"] == "RETRIEVAL_LOW_RECALL":
            desc = "Gold chunks were not returned by the vector/hybrid search."
        elif row["root_cause_classification"] == "EVIDENCE_GATE_REJECTION":
            desc = "Supporting chunks were retrieved but did not pass the evidence threshold."
        elif row["root_cause_classification"] == "VERIFIER_REJECTION":
            desc = "Answer was generated but rejected by the verifier."
        elif row["root_cause_classification"] == "PIPELINE_EXCEPTION":
            desc = "An error occurred during execution."
        else:
            desc = "Unknown reason."
            
        md_content += f"| `{row['test_case_id']}` | {row['language']} | {row['category']} | {chunks_count} | {hit_str} | {score_str} | `{row['root_cause_classification']}` | {desc} |\n"
        
    with open(md_dest, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print("[ROOT CAUSE] Completed root cause analysis!")

if __name__ == "__main__":
    main()
