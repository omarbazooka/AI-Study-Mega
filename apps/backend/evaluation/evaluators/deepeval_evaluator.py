import os
import sys
import json
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from typing import List, Dict, Any

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import yaml
from app.core.config import settings
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_openai import ChatOpenAI

# 1. Custom DeepEval LLM wrapper to route calls to central router
from evaluation.evaluators.centralized_adapters import DeepEvalCentralizedLLM as DeepEvalGroqLLM

def load_config() -> Dict[str, Any]:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "evaluation.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_deepeval_evaluation():
    print("[DEEPEVAL] Starting DeepEval evaluation...")
    
    config = load_config()
    
    # Load raw outputs
    raw_outputs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["raw_outputs"]))
    if not os.path.exists(raw_outputs_path):
        print(f"[DEEPEVAL] ERROR: Raw outputs file '{raw_outputs_path}' not found.")
        sys.exit(1)
        
    records = []
    with open(raw_outputs_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
                
    # Load golden dataset
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["dataset_jsonl"]))
    golden_cases = {}
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                golden_cases[case["test_case_id"]] = case
                
    # DeepEval LLM Judge
    judge_model = config["judge"]["model"]
    custom_judge = DeepEvalGroqLLM(model_name=judge_model)
    
    # Initialize metrics
    relevancy_metric = AnswerRelevancyMetric(threshold=config["thresholds"]["answer_relevancy"], model=custom_judge)
    faithfulness_metric = FaithfulnessMetric(threshold=config["thresholds"]["faithfulness"], model=custom_judge)
    
    educational_quality_metric = GEval(
        name="Educational Answer Quality",
        criteria=(
            "Evaluate the educational answer quality focusing on factual correctness, strict grounding in retrieval context, "
            "clarity, completeness, helpfulness, compliance with intent, and absolute refusal to use outside knowledge."
        ),
        evaluation_steps=[
            "Determine if the response answers the question directly and completely.",
            "Verify that every factual claim is strictly supported by the retrieval context.",
            "Penalize the output heavily if it introduces outside general knowledge.",
            "Verify the explanation is clear and suitable for students.",
            "Assign a final grade from 0 to 1 based on these dimensions."
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
        model=custom_judge,
        threshold=config["thresholds"]["educational_quality"]
    )
    
    # Deterministic Selection of Faithfulness Cross-Check Subset (10 cases)
    # Direct Factual (3), Explanation (2), Multi-chunk (2), Comparison (1), Unanswerable (2)
    factual_cases = [r for r in records if golden_cases.get(r["test_case_id"], {}).get("category") == "direct_factual"]
    explain_cases = [r for r in records if golden_cases.get(r["test_case_id"], {}).get("category") == "explanation"]
    multi_cases = [r for r in records if golden_cases.get(r["test_case_id"], {}).get("category") == "multi_chunk"]
    compare_cases = [r for r in records if golden_cases.get(r["test_case_id"], {}).get("category") == "comparison"]
    unans_cases = [r for r in records if golden_cases.get(r["test_case_id"], {}).get("category") == "unanswerable"]
    
    subset_records = (
        factual_cases[:3] +
        explain_cases[:2] +
        multi_cases[:2] +
        compare_cases[:1] +
        unans_cases[:2]
    )
    subset_ids = {r["test_case_id"] for r in subset_records}
    
    print(f"[DEEPEVAL] Selected {len(subset_ids)} cases for Faithfulness cross-check.")
    
    # Helper to check if actual answer is a refusal / fallback
    def is_refusal_answer(ans: str) -> bool:
        ans_lower = ans.lower()
        refusal_keywords = [
            "لم أجد إجابة", "لا يحتوي الملف", "لا يوجد", "خارج نطاق",
            "does not provide enough supporting evidence",
            "couldn't find details supporting",
            "could not find", "cannot find", "unable to find",
            "no relevant context", "out of scope",
            "does not contain information"
        ]
        return any(kw in ans_lower or kw in ans for kw in refusal_keywords)

    case_results = []
    
    for idx, r in enumerate(records):
        case_id = r["test_case_id"]
        golden = golden_cases.get(case_id)
        if not golden:
            continue
            
        ref_ans = golden.get("reference_answer")
        if ref_ans is None:
            ref_ans = "لم أجد إجابة واضحة في الملف المرفوع." if golden["language"] == "ar" else "I couldn't find a clear answer in the uploaded document."
            
        actual_output = r["actual_answer"]
        is_refusal = is_refusal_answer(actual_output)
        is_answerable = golden.get("answerable", True)
        
        # Create LLMTestCase
        test_case = LLMTestCase(
            input=r["question"],
            actual_output=actual_output,
            expected_output=ref_ans,
            retrieval_context=r["retrieved_contexts"] if r["retrieved_contexts"] else [""]
        )
        
        print(f"[DEEPEVAL] [{idx+1}/{len(records)}] Evaluating {case_id}...")
        
        # Route based on refusal/answerable status to avoid judge errors on empty/fallback text
        if not is_answerable or is_refusal:
            eval_type = "programmatic"
            if not is_answerable:
                if is_refusal:
                    # Correct refusal of unanswerable case
                    relevancy_score = 1.0
                    relevancy_reason = "Correctly refused to answer an unanswerable question."
                    edu_score = 1.0
                    edu_reason = "Correct fallback behavior."
                    faith_score = None  # Refusals are not applicable for faithfulness
                    faith_reason = "Faithful refusal (not applicable)."
                else:
                    # Hallucination on unanswerable case
                    relevancy_score = 0.0
                    relevancy_reason = "Hallucinated an answer for an unanswerable question."
                    edu_score = 0.0
                    edu_reason = "Failed to fall back correctly."
                    faith_score = 0.0 if case_id in subset_ids else None
                    faith_reason = "Unsupported hallucination." if case_id in subset_ids else None
            else:
                # Answerable case that got refused (False Refusal)
                relevancy_score = 0.0
                relevancy_reason = "Failed to answer an answerable question (False Refusal)."
                edu_score = 0.0
                edu_reason = "Refused to answer."
                # False refusal means no claims were made, so it cannot be unfaithful,
                # but it is not_applicable for faithfulness framework metric.
                faith_score = None
                faith_reason = "Refusal (not applicable for faithfulness metric)."
        else:
            # 1. Answer Relevancy
            relevancy_score = 0.0
            relevancy_reason = ""
            try:
                relevancy_metric.measure(test_case)
                relevancy_score = relevancy_metric.score
                relevancy_reason = relevancy_metric.reason
            except Exception as e:
                print(f"[DEEPEVAL] Warning: Relevancy failed for {case_id}: {e}")
                relevancy_score = 0.0
                
            # 2. Educational Answer Quality GEval
            edu_score = 0.0
            edu_reason = ""
            try:
                educational_quality_metric.measure(test_case)
                edu_score = educational_quality_metric.score
                edu_reason = educational_quality_metric.reason
            except Exception as e:
                print(f"[DEEPEVAL] Warning: GEval failed for {case_id}: {e}")
                edu_score = 0.0
                
            # 3. Faithfulness Cross-Check
            faith_score = None
            faith_reason = None
            eval_type = "framework_evaluated"
            if case_id in subset_ids:
                try:
                    faithfulness_metric.measure(test_case)
                    faith_score = faithfulness_metric.score
                    faith_reason = faithfulness_metric.reason
                except Exception as e:
                    print(f"[DEEPEVAL] Warning: Faithfulness failed for {case_id}: {e}")
                    faith_score = None  # Set to None on error to avoid distoring framework averages
                    
        case_results.append({
            "test_case_id": case_id,
            "answer_relevancy": relevancy_score,
            "answer_relevancy_reason": relevancy_reason,
            "educational_quality": edu_score,
            "educational_quality_reason": edu_reason,
            "deepeval_faithfulness": faith_score,
            "deepeval_faithfulness_reason": faith_reason,
            "evaluation_type": eval_type
        })
        
    # Save results to CSV
    results_df = pd.DataFrame(case_results)
    deepeval_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["deepeval_results_csv"]))
    os.makedirs(os.path.dirname(deepeval_csv_path), exist_ok=True)
    results_df.to_csv(deepeval_csv_path, index=False, encoding="utf-8")
    
    # Save summary JSON — compute means ONLY over framework_evaluated cases
    fw_df = results_df[results_df["evaluation_type"] == "framework_evaluated"]
    
    def safe_mean(series):
        valid = series.dropna()
        return float(valid.mean()) if len(valid) > 0 else None

    summary = {
        "framework_evaluated_count": len(fw_df),
        "programmatic_count": len(results_df) - len(fw_df),
        "mean_answer_relevancy": safe_mean(fw_df["answer_relevancy"]),
        "mean_educational_quality": safe_mean(fw_df["educational_quality"]),
        "mean_crosscheck_faithfulness": safe_mean(fw_df["deepeval_faithfulness"]),
        "note": "Means computed only over framework_evaluated cases; programmatic scores excluded from framework averages."
    }
    deepeval_summary_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["deepeval_summary_json"]))
    with open(deepeval_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    # Save metadata JSON
    metadata = {
        "judge_model": judge_model,
        "judge_provider": "groq",
        "deepeval_version": "4.0.6",
        "evaluation_timestamp": pd.Timestamp.now().isoformat(),
        "metrics_run": ["answer_relevancy", "educational_quality", "crosscheck_faithfulness"]
    }
    deepeval_metadata_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["deepeval_metadata_json"]))
    with open(deepeval_metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"[DEEPEVAL] SUCCESS: DeepEval evaluation complete!")
    print(f"[DEEPEVAL] Results CSV: {deepeval_csv_path}")
    print(f"[DEEPEVAL] Summary JSON: {deepeval_summary_path}")

if __name__ == "__main__":
    run_deepeval_evaluation()
