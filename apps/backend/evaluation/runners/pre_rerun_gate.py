"""
pre_rerun_gate.py
-----------------
Aggregates all pre-rerun gate results into pre_rerun_gate.json.
All gates must pass before controlled evaluation rerun is authorized.

Run from apps/backend/:
    python evaluation/runners/pre_rerun_gate.py
"""
import json
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent  # apps/backend
GATE_PATH = ROOT / "evaluation" / "results" / "diagnostics" / "pre_rerun_gate.json"
SMOKE_RESULTS_PATH = ROOT / "evaluation" / "results" / "diagnostics" / "smoke_test_results.json"
UNIT_RESULTS_PATH = ROOT / "evaluation" / "results" / "diagnostics" / "pytest_results.json"

def load_smoke_results():
    if SMOKE_RESULTS_PATH.exists():
        with open(SMOKE_RESULTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("smoke_test_status") == "passed", data
    return False, {"error": "smoke_test_results.json not found"}

def run_unit_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "evaluation/tests/test_fallback_and_metrics.py",
         "-v", "--tb=short"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout + result.stderr
    passed_count = output.count(" PASSED")
    failed_count = output.count(" FAILED")
    return result.returncode == 0, output, passed_count, failed_count

def check_dataset_integrity():
    dataset_path = ROOT / "evaluation" / "datasets" / "golden_dataset.jsonl"
    if not dataset_path.exists():
        return False, "Golden dataset not found"
    with open(dataset_path, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    approved = [c for c in cases if c.get("review_status") == "approved"]
    placeholder_kw = ["template fallback", "احتياطي", "(placeholder)", "Question about ..."]
    bad = [c for c in approved if any(kw in c.get("question", "") for kw in placeholder_kw)]
    if bad:
        return False, f"{len(bad)} approved cases contain placeholder text"
    return True, f"{len(approved)} approved, 0 placeholders"

def check_evidence_gate_imports():
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "from app.ai_system.validation.evidence_gate import validate_evidence, _normalize_score; "
             "from app.ai_system.validation.schemas import EvidenceStatus; "
             "print('OK')"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return False, str(e)

def main():
    gates = {}
    all_passed = True

    print("[PRE-RERUN GATE] Checking all gates...\n")

    # Gate 1: Smoke tests
    smoke_ok, smoke_data = load_smoke_results()
    gates["smoke_tests"] = {
        "passed": smoke_ok,
        "details": smoke_data.get("passed", 0) if isinstance(smoke_data, dict) else 0,
        "total": smoke_data.get("total_scenarios", 8) if isinstance(smoke_data, dict) else 8,
        "status": "PASS" if smoke_ok else "FAIL",
    }
    if not smoke_ok:
        all_passed = False
    print(f"  Gate 1 -- Smoke tests: {'PASS' if smoke_ok else 'FAIL'}")

    # Gate 2: Unit tests
    unit_ok, unit_output, passed_count, failed_count = run_unit_tests()
    gates["unit_tests"] = {
        "passed": unit_ok,
        "tests_passed": passed_count,
        "tests_failed": failed_count,
        "status": "PASS" if unit_ok else "FAIL",
    }
    if not unit_ok:
        all_passed = False
    print(f"  Gate 2 -- Unit tests: {'PASS' if unit_ok else 'FAIL'} ({passed_count} passed, {failed_count} failed)")

    # Gate 3: Dataset integrity
    ds_ok, ds_msg = check_dataset_integrity()
    gates["dataset_integrity"] = {
        "passed": ds_ok,
        "message": ds_msg,
        "status": "PASS" if ds_ok else "FAIL",
    }
    if not ds_ok:
        all_passed = False
    print(f"  Gate 3 -- Dataset integrity: {'PASS' if ds_ok else 'FAIL'} ({ds_msg})")

    # Gate 4: Evidence gate imports
    eg_ok, eg_msg = check_evidence_gate_imports()
    gates["evidence_gate_imports"] = {
        "passed": eg_ok,
        "message": eg_msg,
        "status": "PASS" if eg_ok else "FAIL",
    }
    if not eg_ok:
        all_passed = False
    print(f"  Gate 4 -- Evidence gate imports: {'PASS' if eg_ok else 'FAIL'} ({eg_msg})")

    # Save gate results
    gate_result = {
        "pre_rerun_gate_status": "PASS" if all_passed else "FAIL",
        "rerun_authorized": all_passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gates": gates,
    }

    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GATE_PATH, "w", encoding="utf-8") as f:
        json.dump(gate_result, f, indent=2)

    print(f"\n[PRE-RERUN GATE] Overall: {'PASS -- Rerun authorized.' if all_passed else 'FAIL -- Fix issues before rerun.'}")
    print(f"[PRE-RERUN GATE] Gate file: {GATE_PATH}")
    return all_passed

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
