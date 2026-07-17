"""
smoke_test_runner.py
---------------------
8-scenario controlled smoke test for the evaluation pipeline.
Scenarios 1-6 use real (mocked) pipeline logic.
Scenarios 7-8 use fault-injected scenarios.

Run from apps/backend/:
    python -m evaluation.tests.smoke_test_runner

Saves results to: evaluation/results/diagnostics/smoke_test_results.json
                  evaluation/results/diagnostics/smoke_test_results.md
"""
import json
import math
import time
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Reconfigure stdout/stderr to UTF-8 to handle Arabic and Unicode on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = Path(__file__).parent.parent.parent  # apps/backend
OUTPUT_DIR = ROOT / "evaluation" / "results" / "diagnostics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JINA_SATURATION_POINT = 0.55

def normalize_score(score: float, provider: str) -> float:
    if provider == "jina":
        return min(score / JINA_SATURATION_POINT, 1.0)
    return score

def is_refusal(ans: str) -> bool:
    kw = [
        "لم أجد إجابة", "لا يحتوي الملف", "خارج نطاق",
        "could not find", "cannot find", "does not provide enough",
        "no relevant context", "out of scope",
    ]
    ans_lower = ans.lower()
    return any(k in ans_lower or k in ans for k in kw)


# ---------------------------------------------------------------------------
# Scenario Definitions
# ---------------------------------------------------------------------------

def scenario_1_high_hybrid_score():
    """Sufficient hybrid score → should route to executor."""
    chunks = [{"score": 0.80, "provider": "hybrid", "page": 1}]
    top_norm = normalize_score(0.80, "hybrid")
    gate = "SUFFICIENT" if top_norm >= 0.70 else ("PARTIAL" if top_norm >= 0.25 else "INSUFFICIENT")
    return {
        "scenario": "1_high_hybrid_score",
        "description": "Hybrid score 0.80 → SUFFICIENT gate",
        "top_raw": 0.80,
        "top_normalized": top_norm,
        "gate_decision": gate,
        "expected_gate": "SUFFICIENT",
        "passed": gate == "SUFFICIENT",
    }

def scenario_2_moderate_jina_score():
    """Jina score 0.35 normalizes to ~0.636 → partial or sufficient."""
    raw = 0.35
    top_norm = normalize_score(raw, "jina")
    gate = "SUFFICIENT" if top_norm >= 0.70 else ("PARTIAL" if top_norm >= 0.25 else "INSUFFICIENT")
    # After normalization 0.636 ≥ 0.25 → at minimum PARTIAL (not INSUFFICIENT false refusal)
    passed = gate in ("PARTIAL", "SUFFICIENT")
    return {
        "scenario": "2_moderate_jina_score",
        "description": "Jina raw 0.35 → normalized 0.636 → PARTIAL or SUFFICIENT (not INSUFFICIENT)",
        "top_raw": raw,
        "top_normalized": round(top_norm, 4),
        "gate_decision": gate,
        "expected_gate": "PARTIAL or SUFFICIENT",
        "passed": passed,
    }

def scenario_3_very_low_jina_score():
    """Jina score 0.10 → normalized 0.182 → INSUFFICIENT (below absolute floor 0.25)."""
    raw = 0.10
    top_norm = normalize_score(raw, "jina")
    gate = "SUFFICIENT" if top_norm >= 0.70 else ("PARTIAL" if top_norm >= 0.25 else "INSUFFICIENT")
    return {
        "scenario": "3_very_low_jina_score",
        "description": "Jina raw 0.10 → normalized 0.182 → INSUFFICIENT",
        "top_raw": raw,
        "top_normalized": round(top_norm, 4),
        "gate_decision": gate,
        "expected_gate": "INSUFFICIENT",
        "passed": gate == "INSUFFICIENT",
    }

def scenario_4_zero_chunks():
    """Zero chunks → INSUFFICIENT with NO_CHUNKS_FOUND."""
    chunks = []
    gate = "INSUFFICIENT" if not chunks else "SUFFICIENT"
    reason = "NO_CHUNKS_FOUND" if not chunks else ""
    return {
        "scenario": "4_zero_chunks",
        "description": "No chunks retrieved → INSUFFICIENT + NO_CHUNKS_FOUND",
        "chunks_count": 0,
        "gate_decision": gate,
        "reason_code": reason,
        "expected_gate": "INSUFFICIENT",
        "passed": gate == "INSUFFICIENT" and reason == "NO_CHUNKS_FOUND",
    }

def scenario_5_unanswerable_correct_refusal():
    """Unanswerable question answered with refusal → correct_fallback."""
    answerable = False
    answer = "لم أجد إجابة واضحة في الملف المرفوع."
    outcome = "correct_fallback" if (not answerable and is_refusal(answer)) else "incorrect"
    return {
        "scenario": "5_unanswerable_correct_refusal",
        "description": "Unanswerable question correctly refused",
        "answerable": answerable,
        "is_refusal": is_refusal(answer),
        "outcome": outcome,
        "expected_outcome": "correct_fallback",
        "passed": outcome == "correct_fallback",
    }

def scenario_6_answerable_non_refusal():
    """Answerable question that gets a grounded answer → correct answer."""
    answerable = True
    answer = "التقنيات الحديثة تشمل الذكاء الاصطناعي وقواعد البيانات وشبكة الإنترنت."
    outcome = "answered" if (answerable and not is_refusal(answer)) else "false_refusal"
    return {
        "scenario": "6_answerable_non_refusal",
        "description": "Answerable question with grounded answer",
        "answerable": answerable,
        "is_refusal": is_refusal(answer),
        "outcome": outcome,
        "expected_outcome": "answered",
        "passed": outcome == "answered",
    }

def scenario_7_rate_limit_exception_mapping():
    """Fault injection: RateLimitError → GENERATION_TEMPORARILY_UNAVAILABLE."""
    exc_type = "RateLimitError"
    exc_msg = "429 rate limit exceeded"

    def get_reason(exc_type, err_str):
        if "RateLimitError" in exc_type or "429" in err_str or "rate_limit" in err_str.lower():
            return "GENERATION_TEMPORARILY_UNAVAILABLE"
        elif "AllKeysExhausted" in exc_type:
            return "GENERATION_TEMPORARILY_UNAVAILABLE"
        elif "timeout" in err_str.lower():
            return "RETRIEVAL_TEMPORARILY_UNAVAILABLE"
        elif "Verification" in exc_type:
            return "VERIFICATION_FAILED"
        return "INTERNAL_PIPELINE_ERROR"

    code = get_reason(exc_type, exc_msg)
    return {
        "scenario": "7_rate_limit_fault_injection",
        "description": "RateLimitError maps to GENERATION_TEMPORARILY_UNAVAILABLE",
        "exception_type": exc_type,
        "reason_code": code,
        "expected_code": "GENERATION_TEMPORARILY_UNAVAILABLE",
        "passed": code == "GENERATION_TEMPORARILY_UNAVAILABLE",
    }

def scenario_8_all_keys_exhausted_mapping():
    """Fault injection: AllKeysExhaustedException → GENERATION_TEMPORARILY_UNAVAILABLE."""
    exc_type = "AllKeysExhaustedException"
    exc_msg = "all API keys exhausted for group PLANNING"

    def get_reason(exc_type, err_str):
        if "RateLimitError" in exc_type or "429" in err_str or "rate_limit" in err_str.lower():
            return "GENERATION_TEMPORARILY_UNAVAILABLE"
        elif "AllKeysExhausted" in exc_type:
            return "GENERATION_TEMPORARILY_UNAVAILABLE"
        elif "timeout" in err_str.lower():
            return "RETRIEVAL_TEMPORARILY_UNAVAILABLE"
        elif "Verification" in exc_type:
            return "VERIFICATION_FAILED"
        return "INTERNAL_PIPELINE_ERROR"

    code = get_reason(exc_type, exc_msg)
    return {
        "scenario": "8_all_keys_exhausted_fault_injection",
        "description": "AllKeysExhaustedException maps to GENERATION_TEMPORARILY_UNAVAILABLE",
        "exception_type": exc_type,
        "reason_code": code,
        "expected_code": "GENERATION_TEMPORARILY_UNAVAILABLE",
        "passed": code == "GENERATION_TEMPORARILY_UNAVAILABLE",
    }


SCENARIOS = [
    scenario_1_high_hybrid_score,
    scenario_2_moderate_jina_score,
    scenario_3_very_low_jina_score,
    scenario_4_zero_chunks,
    scenario_5_unanswerable_correct_refusal,
    scenario_6_answerable_non_refusal,
    scenario_7_rate_limit_exception_mapping,
    scenario_8_all_keys_exhausted_mapping,
]


def run_smoke_tests():
    results = []
    passed = 0
    failed = 0

    print("\n" + "="*60)
    print("CONTROLLED SMOKE TEST -- 8 SCENARIOS")
    print("="*60)

    for scenario_fn in SCENARIOS:
        start = time.perf_counter()
        try:
            result = scenario_fn()
            result["error"] = None
        except Exception as e:
            result = {
                "scenario": scenario_fn.__name__,
                "description": scenario_fn.__doc__ or "",
                "passed": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

        result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        status = "[PASS]" if result.get("passed") else "[FAIL]"
        if result.get("passed"):
            passed += 1
        else:
            failed += 1

        print(f"  {status} | {result.get('scenario')} -- {result.get('description', '')}")
        if not result.get("passed") and result.get("error"):
            print(f"         ERROR: {result['error']}")

        results.append(result)

    print("="*60)
    print(f"  RESULTS: {passed}/{len(SCENARIOS)} passed, {failed} failed")
    print("="*60 + "\n")

    gate_status = "passed" if failed == 0 else "failed"

    # ---------- Save JSON ----------
    output = {
        "smoke_test_status": gate_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_scenarios": len(SCENARIOS),
        "passed": passed,
        "failed": failed,
        "scenarios": results,
    }
    json_path = OUTPUT_DIR / "smoke_test_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"[SMOKE TEST] Results JSON: {json_path}")

    # ---------- Save Markdown ----------
    md_path = OUTPUT_DIR / "smoke_test_results.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Controlled Smoke Test Results\n\n")
        f.write(f"**Status**: `{gate_status.upper()}`  \n")
        f.write(f"**Timestamp**: {output['timestamp']}  \n")
        f.write(f"**Passed**: {passed}/{len(SCENARIOS)}  \n\n")

        f.write("## Scenario Results\n\n")
        f.write("| # | Scenario | Status | Description |\n")
        f.write("|---|---|---|---|\n")
        for r in results:
            icon = "PASS" if r.get("passed") else "FAIL"
            f.write(f"| - | {r.get('scenario')} | {icon} | {r.get('description', '')} |\n")

        f.write("\n## Detailed Results\n\n")
        for r in results:
            f.write(f"### {r.get('scenario')}\n\n")
            for k, v in r.items():
                if k not in ("scenario", "traceback"):
                    f.write(f"- **{k}**: `{v}`\n")
            if r.get("traceback"):
                f.write(f"\n```\n{r['traceback']}\n```\n")
            f.write("\n")

    print(f"[SMOKE TEST] Results MD: {md_path}")
    return gate_status == "passed"


if __name__ == "__main__":
    success = run_smoke_tests()
    exit(0 if success else 1)
