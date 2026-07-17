import os
import shutil
import json
import hashlib
import subprocess

def get_file_hash(path):
    if not os.path.exists(path):
        return "not_found"
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"

def main():
    print("[BASELINE] Creating baseline snapshot...")
    
    backend_dir = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
    run_id = "run_20260714_1100"
    
    results_base = os.path.join(backend_dir, "evaluation", "results", "baselines", run_id)
    reports_base = os.path.join(backend_dir, "evaluation", "reports", "baselines", run_id)
    
    os.makedirs(results_base, exist_ok=True)
    os.makedirs(reports_base, exist_ok=True)
    
    # Files/directories to copy to results
    results_copies = [
        ("evaluation/results/raw/pipeline_outputs.jsonl", "pipeline_outputs.jsonl"),
        ("evaluation/results/ragas/ragas_case_results.csv", "ragas_case_results.csv"),
        ("evaluation/results/ragas/ragas_summary.json", "ragas_summary.json"),
        ("evaluation/results/ragas/ragas_run_metadata.json", "ragas_run_metadata.json"),
        ("evaluation/results/deepeval/deepeval_case_results.csv", "deepeval_case_results.csv"),
        ("evaluation/results/deepeval/deepeval_summary.json", "deepeval_summary.json"),
        ("evaluation/results/deepeval/deepeval_run_metadata.json", "deepeval_run_metadata.json"),
        ("evaluation/results/summary/local_metrics.json", "local_metrics.json"),
        ("evaluation/results/diagnostics/per_case_diagnostics.csv", "per_case_diagnostics.csv"),
        ("evaluation/results/diagnostics/per_case_diagnostics.md", "per_case_diagnostics.md"),
        ("evaluation/results/diagnostics/evidence_score_propagation_audit.csv", "evidence_score_propagation_audit.csv"),
        ("evaluation/results/diagnostics/evidence_score_propagation_audit.md", "evidence_score_propagation_audit.md"),
        ("evaluation/results/diagnostics/false_refusal_root_cause.md", "false_refusal_root_cause.md"),
        ("evaluation/results/diagnostics/smoke_test_results.json", "smoke_test_results.json"),
        ("evaluation/results/diagnostics/smoke_test_results.md", "smoke_test_results.md"),
    ]
    
    for src_rel, dest_name in results_copies:
        src = os.path.join(backend_dir, src_rel)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(results_base, dest_name))
            print(f"  Copied {src_rel} -> results baseline")
            
    # Copy reports and charts
    shutil.copy2(
        os.path.join(backend_dir, "evaluation/reports/AI_STUDY_PLATFORM_EVALUATION_REPORT.md"),
        os.path.join(reports_base, "AI_STUDY_PLATFORM_EVALUATION_REPORT.md")
    )
    shutil.copy2(
        os.path.join(backend_dir, "evaluation/reports/AI_STUDY_PLATFORM_EVALUATION_REPORT.html"),
        os.path.join(reports_base, "AI_STUDY_PLATFORM_EVALUATION_REPORT.html")
    )
    shutil.copy2(
        os.path.join(backend_dir, "evaluation/reports/AI_STUDY_PLATFORM_EVALUATION_REPORT.pdf"),
        os.path.join(reports_base, "AI_STUDY_PLATFORM_EVALUATION_REPORT.pdf")
    )
    
    # Copy charts folder
    charts_src = os.path.join(backend_dir, "evaluation/reports/charts")
    charts_dest = os.path.join(reports_base, "charts")
    if os.path.exists(charts_src):
        if os.path.exists(charts_dest):
            shutil.rmtree(charts_dest)
        shutil.copytree(charts_src, charts_dest)
        print("  Copied charts directory -> reports baseline")
        
    # 3. Create baseline metadata
    dataset_path = os.path.join(backend_dir, "evaluation", "datasets", "golden_dataset.jsonl")
    manifest_path = os.path.join(backend_dir, "evaluation", "datasets", "document_manifest.json")
    
    metadata = {
        "baseline_run_id": run_id,
        "git_commit": get_git_commit(),
        "dataset_hash": get_file_hash(dataset_path),
        "document_set_hash": get_file_hash(manifest_path),
        "production_configuration_hash": hashlib.sha256("evidence_gate_v2_jina_normalized".encode('utf-8')).hexdigest()[:12],
        "evidence_policy_version": "2.0.0",
        "reranker_configuration": "jina-reranker-v3-primary",
        "key_borrowing_configuration": "LLM_ALLOW_CROSS_GROUP_KEY_BORROWING=true",
        "accuracy_labels": {
            "Generated Answer Count": 11,
            "Correctly Answered Count": 10,
            "Incorrect/Hallucinated Generated Count": 1,
            "Answerable Accuracy": "37.04%",
            "Answer Coverage": "40.74%",
            "False Refusal Rate": "59.26%",
            "Correct Fallback Rate": "66.67%",
            "Overall Task Success": "40.00%"
        }
    }
    
    metadata_path = os.path.join(results_base, "baseline_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"[BASELINE] SUCCESS: Baseline snapshot created under {results_base} and {reports_base}")

if __name__ == "__main__":
    main()
