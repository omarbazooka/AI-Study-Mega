"""
evidence_score_propagation_audit.py
------------------------------------
Reads pipeline_outputs.jsonl and exports per-case score propagation traces
to both CSV and Markdown, covering at least 5 representative cases.

Run from apps/backend/:
    python -m evaluation.scratch.evidence_score_propagation_audit
"""
import json
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent  # apps/backend
OUTPUT_DIR = ROOT / "evaluation" / "results" / "diagnostics"
JSONL_PATH = ROOT / "evaluation" / "results" / "raw" / "pipeline_outputs.jsonl"
DATASET_PATH = ROOT / "evaluation" / "datasets" / "golden_dataset.jsonl"

JINA_SATURATION_POINT = 0.55  # Must match evidence_gate.py

def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def normalize_jina(score: float) -> float:
    return min(score / JINA_SATURATION_POINT, 1.0)

def classify_outcome(top_norm: float, answerable: bool, actual_answer: str) -> str:
    refusal_kw = [
        "لم أجد إجابة", "لا يحتوي الملف", "خارج نطاق",
        "could not find", "cannot find", "does not provide enough",
        "no relevant context", "out of scope",
    ]
    is_refusal = any(kw in actual_answer.lower() or kw in actual_answer for kw in refusal_kw)

    if not answerable:
        return "correct_fallback" if is_refusal else "hallucinated_answer"
    if is_refusal:
        return "false_refusal"
    return "answered"

def gate_decision(top_normalized: float, task_type: str) -> str:
    """Mirror the evidence_gate logic for audit purposes (simplified)."""
    ABSOLUTE_FLOOR = 0.25
    if top_normalized < ABSOLUTE_FLOOR:
        return "INSUFFICIENT (below floor)"
    if top_normalized < 0.40:
        return "PARTIAL (weak score)"
    if top_normalized < 0.70:
        return "PARTIAL (moderate score)"
    return "SUFFICIENT"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = load_jsonl(JSONL_PATH)
    golden = {c["test_case_id"]: c for c in load_jsonl(DATASET_PATH)}

    rows = []
    for r in records:
        cid = r["test_case_id"]
        gc = golden.get(cid, {})
        answerable = gc.get("answerable", True)
        category = gc.get("category", "unknown")
        lang = gc.get("language", "?")

        # Scores from pipeline output
        retrieval_scores = r.get("retrieval_scores") or []
        reranker_scores = r.get("reranker_scores") or []
        similarity_score_used = r.get("final_confidence", 0.0)

        # Detect active provider from answer metadata if available
        # (pipeline_outputs.jsonl does not store per-chunk metadata; use heuristics)
        # If reranker_scores is non-empty and max < 0.55, treat as Jina
        top_raw = max(reranker_scores) if reranker_scores else (max(retrieval_scores) if retrieval_scores else 0.0)
        provider = "jina" if (reranker_scores and max(reranker_scores) < 0.56) else (
            "hybrid" if not reranker_scores else "cohere"
        )
        top_normalized = normalize_jina(top_raw) if provider == "jina" else top_raw

        gate = gate_decision(top_normalized, category)
        outcome = classify_outcome(top_normalized, answerable, r.get("actual_answer", ""))

        rows.append({
            "test_case_id": cid,
            "category": category,
            "lang": lang,
            "answerable": answerable,
            "active_provider": provider,
            "top_raw_score": round(top_raw, 4),
            "top_normalized_score": round(top_normalized, 4),
            "retrieval_scores": str(retrieval_scores[:3]),
            "reranker_scores": str(reranker_scores[:3]),
            "gate_decision": gate,
            "actual_outcome": outcome,
            "expected_gate_with_fix": "SUFFICIENT" if (top_normalized >= 0.40 and answerable) else gate,
        })

    # ---------- CSV ----------
    csv_path = OUTPUT_DIR / "evidence_score_propagation_audit.csv"
    fieldnames = list(rows[0].keys()) if rows else []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[AUDIT] CSV saved: {csv_path}")

    # ---------- Markdown ----------
    md_path = OUTPUT_DIR / "evidence_score_propagation_audit.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Evidence Score Propagation Audit\n\n")
        f.write(f"**Cases audited**: {len(rows)}  \n")
        f.write(f"**Jina saturation point**: {JINA_SATURATION_POINT}  \n\n")
        f.write("## Key Findings\n\n")

        false_refusals = [r for r in rows if r["actual_outcome"] == "false_refusal"]
        norm_above_floor = [r for r in false_refusals if r["top_normalized_score"] >= 0.25]
        jina_cases = [r for r in rows if r["active_provider"] == "jina"]

        f.write(f"- **Total false refusals**: {len(false_refusals)} / {len(rows)}\n")
        f.write(f"- **False refusals with score ≥ 0.25 after normalization**: {len(norm_above_floor)}\n")
        f.write(f"- **Cases where Jina reranker detected**: {len(jina_cases)}\n\n")
        f.write("> **Root cause**: Jina reranker returns relevance scores < 0.55 for highly relevant passages.\n")
        f.write("> The evidence gate's hard floor of 0.55 (pre-fix) rejected all reranked chunks.\n")
        f.write("> The fix applies `normalized = raw / 0.55` for Jina scores, mapping 0.35 → 0.636, etc.\n\n")

        f.write("## Score Propagation Table\n\n")
        f.write("| ID | Category | Answerable | Provider | Raw Score | Normalized | Gate Decision | Outcome |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(
                f"| {r['test_case_id']} | {r['category']} | {r['answerable']} | {r['active_provider']} "
                f"| {r['top_raw_score']} | {r['top_normalized_score']} | {r['gate_decision']} | {r['actual_outcome']} |\n"
            )

        f.write("\n## Detailed Case Traces (Representative Sample)\n\n")
        # Select 5 representative: 2 false refusals, 1 correct fallback, 1 answered, 1 cross-lingual
        sample = []
        for outcome_type in ["false_refusal", "correct_fallback", "answered"]:
            candidates = [r for r in rows if r["actual_outcome"] == outcome_type]
            if candidates:
                sample.append(candidates[0])
        # cross-lingual
        cross = [r for r in rows if r["lang"] not in ("ar", "en")]
        if cross:
            sample.append(cross[0])
        # add one more false refusal if we have it
        fr = [r for r in rows if r["actual_outcome"] == "false_refusal"]
        if len(fr) > 1 and fr[1] not in sample:
            sample.append(fr[1])
        sample = sample[:5]

        for r in sample:
            f.write(f"### {r['test_case_id']} — {r['category']} ({r['lang']})\n\n")
            for k, v in r.items():
                f.write(f"- **{k}**: `{v}`\n")
            f.write("\n")

    print(f"[AUDIT] Markdown saved: {md_path}")
    print(f"\n[AUDIT SUMMARY] False refusals: {len(false_refusals)}/{len(rows)}")
    print(f"[AUDIT SUMMARY] False refusals fixable by normalization: {len(norm_above_floor)}")

if __name__ == "__main__":
    main()
