import os
import re
import json
import math
import pandas as pd
from datetime import datetime, timezone


def _load_json_safe(path: str):
    """Load JSON, replacing bare NaN/Infinity with None so json.loads can parse."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    raw = re.sub(r'\bNaN\b', 'null', raw)
    raw = re.sub(r'\bInfinity\b', 'null', raw)
    raw = re.sub(r'\b-Infinity\b', 'null', raw)
    return json.loads(raw)


def _check_df_for_nan_inf(df: pd.DataFrame, columns: list):
    """Returns (nan_counts, inf_counts) dicts for given columns."""
    nan_counts = {}
    inf_counts = {}
    for col in columns:
        if col in df.columns:
            nan_counts[col] = int(df[col].isna().sum())
            try:
                inf_counts[col] = int(
                    df[col].apply(lambda x: math.isinf(x) if isinstance(x, float) else False).sum()
                )
            except Exception:
                inf_counts[col] = 0
    return nan_counts, inf_counts


def validate_integrity():
    print("[INTEGRITY] Starting data integrity validation gate...")
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    golden_path = os.path.join(backend_dir, "evaluation", "datasets", "golden_dataset.jsonl")
    diagnostics_path = os.path.join(backend_dir, "evaluation", "results", "diagnostics", "per_case_diagnostics.csv")
    ragas_path = os.path.join(backend_dir, "evaluation", "results", "ragas", "ragas_case_results.csv")
    deepeval_path = os.path.join(backend_dir, "evaluation", "results", "deepeval", "deepeval_case_results.csv")
    local_metrics_path = os.path.join(backend_dir, "evaluation", "results", "summary", "local_metrics.json")
    report_path = os.path.join(backend_dir, "evaluation", "results", "summary", "data_integrity_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    checks = {}
    errors = []
    warnings = []

    # ------------------------------------------------------------------
    # Check 1: Golden dataset — must exist with exactly 30 cases
    # ------------------------------------------------------------------
    if os.path.exists(golden_path):
        with open(golden_path, "r", encoding="utf-8") as f:
            golden_count = sum(1 for line in f if line.strip())
        checks["golden_dataset_exists"] = True
        checks["golden_case_count"] = golden_count
        if golden_count != 30:
            errors.append(f"Golden dataset has {golden_count} cases, expected exactly 30.")
    else:
        checks["golden_dataset_exists"] = False
        errors.append("Golden dataset file not found.")

    # ------------------------------------------------------------------
    # Check 2: Diagnostics CSV — 30 rows required
    # ------------------------------------------------------------------
    if os.path.exists(diagnostics_path):
        df_diag = pd.read_csv(diagnostics_path)
        diag_count = len(df_diag)
        checks["diagnostics_exists"] = True
        checks["diagnostics_row_count"] = diag_count
        if diag_count != 30:
            errors.append(f"Diagnostics CSV has {diag_count} rows, expected exactly 30.")
    else:
        checks["diagnostics_exists"] = False
        errors.append("Diagnostics CSV not found.")

    # ------------------------------------------------------------------
    # Check 3: RAGAS results — 30 rows, zero NaN/Inf in framework columns
    # ------------------------------------------------------------------
    if os.path.exists(ragas_path):
        df_ragas = pd.read_csv(ragas_path)
        ragas_count = len(df_ragas)
        checks["ragas_results_exists"] = True
        checks["ragas_row_count"] = ragas_count

        df_fw = df_ragas[df_ragas["evaluation_type"] == "framework_evaluated"] if "evaluation_type" in df_ragas.columns else df_ragas
        nan_counts, inf_counts = _check_df_for_nan_inf(df_fw, ["answer_correctness", "faithfulness"])
        checks["ragas_nan_correctness"] = nan_counts.get("answer_correctness", 0)
        checks["ragas_nan_faithfulness"] = nan_counts.get("faithfulness", 0)
        checks["ragas_inf_correctness"] = inf_counts.get("answer_correctness", 0)
        checks["ragas_inf_faithfulness"] = inf_counts.get("faithfulness", 0)

        if ragas_count != 30:
            errors.append(f"RAGAS CSV has {ragas_count} rows, expected exactly 30.")
        for col, cnt in nan_counts.items():
            if cnt > 0:
                errors.append(f"RAGAS column '{col}' has {cnt} NaN values in framework_evaluated cases.")
        for col, cnt in inf_counts.items():
            if cnt > 0:
                errors.append(f"RAGAS column '{col}' has {cnt} Infinite values in framework_evaluated cases.")
    else:
        checks["ragas_results_exists"] = False
        errors.append("RAGAS results CSV not found.")

    # ------------------------------------------------------------------
    # Check 4: DeepEval results — 30 rows, zero NaN in active metric columns
    # ------------------------------------------------------------------
    if os.path.exists(deepeval_path):
        df_deepeval = pd.read_csv(deepeval_path)
        deepeval_count = len(df_deepeval)
        checks["deepeval_results_exists"] = True
        checks["deepeval_row_count"] = deepeval_count

        df_fw = df_deepeval[df_deepeval["evaluation_type"] == "framework_evaluated"] if "evaluation_type" in df_deepeval.columns else df_deepeval
        nan_counts, inf_counts = _check_df_for_nan_inf(df_fw, ["answer_relevancy", "educational_quality"])
        checks["deepeval_nan_relevancy"] = nan_counts.get("answer_relevancy", 0)
        checks["deepeval_nan_educational"] = nan_counts.get("educational_quality", 0)

        if deepeval_count != 30:
            errors.append(f"DeepEval CSV has {deepeval_count} rows, expected exactly 30.")
        for col, cnt in nan_counts.items():
            if cnt > 0:
                errors.append(f"DeepEval column '{col}' has {cnt} NaN values in framework_evaluated cases.")
        for col, cnt in inf_counts.items():
            if cnt > 0:
                errors.append(f"DeepEval column '{col}' has {cnt} Infinite values in framework_evaluated cases.")
    else:
        checks["deepeval_results_exists"] = False
        errors.append("DeepEval results CSV not found.")

    # ------------------------------------------------------------------
    # Check 5: Local metrics — confusion matrix sum = 30, no NaN/inf
    # ------------------------------------------------------------------
    if os.path.exists(local_metrics_path):
        local = _load_json_safe(local_metrics_path)
        matrix = local.get("confusion_matrix", {})
        cm_sum = sum(matrix.values())
        checks["local_metrics_exists"] = True
        checks["confusion_matrix_sum"] = cm_sum

        if cm_sum != 30:
            errors.append(f"Confusion matrix sum is {cm_sum}, expected exactly 30.")

        nan_fields = []
        for key in ["correct_answer_rate", "hallucination_case_rate", "mean_response_latency_ms"]:
            val = local.get(key)
            if val is None:
                nan_fields.append(key)
        if nan_fields:
            warnings.append(f"Local metrics contain null values for: {nan_fields}")

        composite = local.get("project_defined_composite_score")
        if composite is not None and isinstance(composite, float) and math.isnan(composite):
            errors.append("project_defined_composite_score is NaN. Should be null when components are missing.")
    else:
        checks["local_metrics_exists"] = False
        errors.append("Local metrics summary JSON not found.")

    # ------------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------------
    status = "passed" if not errors else "failed"
    checks["data_integrity_status"] = status
    checks["errors"] = errors
    checks["warnings"] = warnings
    checks["timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(checks, f, indent=2)

    print(f"[INTEGRITY] Integrity status: {status.upper()}")
    if errors:
        for err in errors:
            print(f"  [ERROR] {err}")
    if warnings:
        for w in warnings:
            print(f"  [WARN]  {w}")
    if not errors:
        print("[INTEGRITY] All checks passed successfully!")

    return status == "passed"


if __name__ == "__main__":
    ok = validate_integrity()
    exit(0 if ok else 1)
