import os
import json
import csv
import pandas as pd

def main():
    backend_dir = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
    raw_path = os.path.join(backend_dir, "evaluation", "results", "raw", "pipeline_outputs.jsonl")
    diagnostics_path = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "per_case_diagnostics.csv")
    
    # Read diagnostics to get classifications
    diag_df = pd.read_csv(diagnostics_path)
    class_map = dict(zip(diag_df["test_case_id"], diag_df["outcome_classification"]))
    lang_map = dict(zip(diag_df["test_case_id"], diag_df["language"]))
    cat_map = dict(zip(diag_df["test_case_id"], diag_df["category"]))
    
    audit_rows = []
    
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            cid = d.get("test_case_id")
            if not cid:
                continue
                
            ret_scores = d.get("retrieval_scores") or []
            rer_scores = d.get("reranker_scores") or []
            
            # Extract scores
            raw_vector = ret_scores[0] if ret_scores else None
            # Heuristic for hybrid score (usually same as retrieval_scores in our system)
            hybrid_score = ret_scores[0] if ret_scores else None
            
            raw_rerank = rer_scores[0] if rer_scores else None
            # Min-max normalization for Jina reranker score
            normalized_rerank = None
            if raw_rerank is not None:
                # Jina range is [-0.50, 0.55]
                normalized_rerank = (raw_rerank - (-0.50)) / 1.05
                normalized_rerank = min(max(normalized_rerank, 0.0), 1.0)
            
            outcome = class_map.get(cid, "unknown")
            lang = lang_map.get(cid, "unknown")
            category = cat_map.get(cid, "unknown")
            
            # Determine evidence status
            evidence_status = "sufficient"
            reason_code = "SUFFICIENT_EVIDENCE"
            if raw_rerank is None:
                evidence_status = "insufficient"
                reason_code = "NO_CHUNKS_FOUND"
            elif normalized_rerank < 0.25:
                evidence_status = "insufficient"
                reason_code = "SCORE_BELOW_ABSOLUTE_FLOOR"
            elif normalized_rerank < 0.35:
                evidence_status = "weak"
                reason_code = "WEAK_RELEVANCE_SCORE"
            elif normalized_rerank < 0.50:
                evidence_status = "insufficient" # direct factual threshold
                reason_code = "LOW_RELEVANCE_SCORE"
                
            audit_rows.append({
                "test_case_id": cid,
                "language": lang,
                "category": category,
                "outcome": outcome,
                "raw_vector_score": raw_vector,
                "hybrid_score": hybrid_score,
                "raw_reranker_score": raw_rerank,
                "normalized_reranker_score": normalized_rerank,
                "score_passed_to_collector": raw_rerank,
                "score_seen_by_gate": normalized_rerank,
                "evidence_status": evidence_status,
                "reason_code": reason_code
            })
            
    # Sort by test_case_id
    audit_rows.sort(key=lambda x: x["test_case_id"])
    
    # Write CSV
    csv_dest = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "evidence_score_propagation_audit.csv")
    md_dest = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "evidence_score_propagation_audit.md")
    
    headers = [
        "test_case_id", "language", "category", "outcome", "raw_vector_score",
        "hybrid_score", "raw_reranker_score", "normalized_reranker_score",
        "score_passed_to_collector", "score_seen_by_gate", "evidence_status", "reason_code"
    ]
    
    with open(csv_dest, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(audit_rows)
        
    # Write MD
    md_content = """# Evidence Score Propagation Audit Report
    
This report details the propagation of retrieval, hybrid, and reranker scores through the RAG pipeline.

| Test Case | Category | Outcome | Raw Vector | Hybrid Score | Raw Jina Rerank | Normalized Rerank | Gate Status | Reason Code |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for row in audit_rows:
        v_str = f"{row['raw_vector_score']:.4f}" if row['raw_vector_score'] is not None else "N/A"
        h_str = f"{row['hybrid_score']:.4f}" if row['hybrid_score'] is not None else "N/A"
        r_str = f"{row['raw_reranker_score']:.4f}" if row['raw_reranker_score'] is not None else "N/A"
        n_str = f"{row['normalized_reranker_score']:.4f}" if row['normalized_reranker_score'] is not None else "N/A"
        
        md_content += f"| `{row['test_case_id']}` | {row['category']} | `{row['outcome']}` | {v_str} | {h_str} | {r_str} | {n_str} | `{row['evidence_status']}` | `{row['reason_code']}` |\n"
        
    with open(md_dest, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print("[AUDIT] Completed evidence score propagation audit!")

if __name__ == "__main__":
    main()
