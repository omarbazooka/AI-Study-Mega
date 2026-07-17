import json
import os
import pandas as pd
import numpy as np

PIPELINE_FILE = "evaluation/results/raw/pipeline_outputs.jsonl"
GOLDEN_FILE = "evaluation/datasets/golden_dataset.jsonl"
OUTPUT_DIR = "evaluation/results/optimization"

def parse_jsonl(filepath):
    records = []
    if not os.path.exists(filepath):
        return records
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    pipeline_records = parse_jsonl(PIPELINE_FILE)
    golden_records = parse_jsonl(GOLDEN_FILE)
    
    golden_by_id = {r["test_case_id"]: r for r in golden_records}
    
    refusal_keywords = [
        "لم أجد إجابة", "لا يحتوي الملف", "لا يوجد", "خارج نطاق",
        "does not provide enough supporting evidence",
        "couldn't find details supporting",
        "could not find", "cannot find", "unable to find",
        "no relevant context", "out of scope",
        "does not contain information"
    ]
    
    failures = {}
    
    for p in pipeline_records:
        cid = p["test_case_id"]
        g = golden_by_id.get(cid)
        if not g:
            continue
            
        is_answerable = g.get("answerable", True)
        actual_ans = p.get("actual_answer", "")
        ans_lower = actual_ans.lower()
        is_fallback = any(kw in ans_lower or kw in actual_ans for kw in refusal_keywords) or "fallback" in p.get("verifier_status", "").lower()
        
        has_error = p.get("error") is not None
        
        # We classify this case
        outcome = "correct"
        root_cause = "none"
        detail = "N/A"
        evidence_found_in = []
        
        retrieved_ids = p.get("retrieved_chunk_ids", [])
        ref_ids = g.get("reference_chunk_ids", [])
        
        # Check if reference chunk exists in retrieved
        ref_retrieved = [rid for rid in ref_ids if rid in retrieved_ids]
        
        # Check where evidence existed
        # In raw retrieval (vector + keyword)
        if ref_retrieved:
            evidence_found_in.append("raw_retrieval")
            # Top 5 reranked
            top_5 = retrieved_ids[:5]
            ref_top_5 = [rid for rid in ref_ids if rid in top_5]
            if ref_top_5:
                evidence_found_in.append("reranked_top_5")
                # context
                evidence_found_in.append("final_context")
                evidence_found_in.append("verifier_input")
        
        if has_error:
            outcome = "technical_failure"
            root_cause = "technical_provider_failure"
            detail = f"Pipeline execution failed with error: {p.get('error')}"
        elif is_answerable:
            if is_fallback:
                outcome = "false_refusal"
                # Determine root cause of false refusal
                if not retrieved_ids:
                    root_cause = "vector_retrieval" # Empty retrieval
                    detail = "Retrieval returned zero candidates."
                elif not ref_retrieved:
                    root_cause = "vector_retrieval" # Missed retrieval
                    detail = "Retrieval failed to find the target reference chunks (Recall = 0)."
                elif "reranked_top_5" not in evidence_found_in:
                    root_cause = "reranking"
                    detail = "Target reference chunks were retrieved but filtered out during reranking."
                elif p.get("verifier_status") == "failed":
                    root_cause = "verification"
                    detail = "Grounded context reached verifier but verifier rejected the generation, triggering fallback."
                else:
                    root_cause = "evidence_gate"
                    detail = "Evidence was present in context but failed evidence gate validation (e.g. threshold below floor)."
            else:
                # Substantive answer generated. Check if it passed verifier/correctness?
                # We can't evaluate correctness here since Ragas is NaN. Let's assume correct if no other indicators,
                # or check if it was checked
                pass
        else: # unanswerable
            if not is_fallback:
                outcome = "hallucination"
                root_cause = "evidence_gate" # Should have fallen back
                detail = "System generated answer for unanswerable case instead of falling back."
                
        if outcome != "correct":
            failures[cid] = {
                "test_case_id": cid,
                "outcome": outcome,
                "root_cause": root_cause,
                "detail": detail,
                "evidence_found_in": evidence_found_in,
                "expected_reference_chunk_ids": ref_ids,
                "retrieved_chunk_ids": retrieved_ids,
                "verifier_status": p.get("verifier_status"),
                "verifier_action": p.get("verifier_action")
            }

    # Group failures
    by_root_cause = {}
    for cid, f in failures.items():
        by_root_cause.setdefault(f["root_cause"], []).append(f)
        
    analysis_json = {
        "failures": failures,
        "grouped_by_root_cause": by_root_cause,
        "summary": {
            "total_failed_cases": len(failures),
            "by_root_cause_counts": {k: len(v) for k, v in by_root_cause.items()}
        }
    }
    
    with open(f"{OUTPUT_DIR}/error_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_json, f, indent=2)
        
    # Write Markdown report
    with open(f"{OUTPUT_DIR}/error_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Zero-Token Local Root-Cause Analysis\n\n")
        f.write(f"Total Failed/False Refusal Cases Analyzed: {len(failures)}\n\n")
        
        f.write("## Summary of Failures by Root Cause\n")
        for k, v in by_root_cause.items():
            f.write(f"- **{k}**: {len(v)} cases\n")
        f.write("\n")
        
        f.write("## Detailed Case Analysis\n")
        for cid, info in failures.items():
            f.write(f"### {cid} ({info['outcome']})\n")
            f.write(f"- **Root Cause**: {info['root_cause']}\n")
            f.write(f"- **Detail**: {info['detail']}\n")
            f.write(f"- **Evidence Found In**: {', '.join(info['evidence_found_in']) if info['evidence_found_in'] else 'None'}\n")
            f.write(f"- **Expected Chunks**: {info['expected_reference_chunk_ids']}\n")
            f.write(f"- **Retrieved Chunks**: {info['retrieved_chunk_ids'][:5]} (showing top 5)\n")
            f.write("\n")

if __name__ == "__main__":
    main()
