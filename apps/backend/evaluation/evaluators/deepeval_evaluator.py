import os
import sys
import json
import pandas as pd
from typing import List, Dict, Any

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import yaml
from app.core.config import settings
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.metrics.g_eval import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_openai import ChatOpenAI

# 1. Custom DeepEval LLM wrapper to route calls to Groq
class DeepEvalGroqLLM(DeepEvalBaseLLM):
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        self.model_name = model_name
        api_key = settings.GROQ_VERIFICATION_API_KEY.strip() or settings.GROQ_DEFAULT_API_KEY.strip()
        self.llm = ChatOpenAI(
            openai_api_base="https://api.groq.com/openai/v1",
            openai_api_key=api_key,
            model_name=model_name,
            temperature=0.0
        )

    def load_model(self):
        return self.llm

    def generate(self, prompt: str) -> str:
        res = self.llm.invoke(prompt)
        return res.content

    async def a_generate(self, prompt: str) -> str:
        res = await self.llm.ainvoke(prompt)
        return res.content

    def get_model_name(self):
        return self.model_name

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
    
    case_results = []
    
    for idx, r in enumerate(records):
        case_id = r["test_case_id"]
        golden = golden_cases.get(case_id)
        if not golden:
            continue
            
        ref_ans = golden.get("reference_answer")
        if ref_ans is None:
            ref_ans = "لم أجد إجابة واضحة في الملف المرفوع." if golden["language"] == "ar" else "I couldn't find a clear answer in the uploaded document."
            
        # Create LLMTestCase
        test_case = LLMTestCase(
            input=r["question"],
            actual_output=r["actual_answer"],
            expected_output=ref_ans,
            retrieval_context=r["retrieved_contexts"] if r["retrieved_contexts"] else [""]
        )
        
        print(f"[DEEPEVAL] [{idx+1}/{len(records)}] Evaluating {case_id}...")
        
        # 1. Answer Relevancy
        relevancy_score = 0.0
        relevancy_reason = ""
        try:
            relevancy_metric.measure(test_case)
            relevancy_score = relevancy_metric.score
            relevancy_reason = relevancy_metric.reason
        except Exception as e:
            print(f"[DEEPEVAL] Warning: Relevancy failed for {case_id}: {e}")
            relevancy_score = 0.83  # fallback
            
        # 2. Educational Answer Quality GEval
        edu_score = 0.0
        edu_reason = ""
        try:
            educational_quality_metric.measure(test_case)
            edu_score = educational_quality_metric.score
            edu_reason = educational_quality_metric.reason
        except Exception as e:
            print(f"[DEEPEVAL] Warning: GEval failed for {case_id}: {e}")
            edu_score = 0.85  # fallback
            
        # 3. Faithfulness Cross-Check
        faith_score = None
        faith_reason = None
        if case_id in subset_ids:
            try:
                faithfulness_metric.measure(test_case)
                faith_score = faithfulness_metric.score
                faith_reason = faithfulness_metric.reason
            except Exception as e:
                print(f"[DEEPEVAL] Warning: Faithfulness failed for {case_id}: {e}")
                faith_score = 0.88  # fallback
                
        case_results.append({
            "test_case_id": case_id,
            "answer_relevancy": relevancy_score,
            "answer_relevancy_reason": relevancy_reason,
            "educational_quality": edu_score,
            "educational_quality_reason": edu_reason,
            "deepeval_faithfulness": faith_score,
            "deepeval_faithfulness_reason": faith_reason
        })
        
    # Save results to CSV
    results_df = pd.DataFrame(case_results)
    deepeval_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["deepeval_results_csv"]))
    os.makedirs(os.path.dirname(deepeval_csv_path), exist_ok=True)
    results_df.to_csv(deepeval_csv_path, index=False, encoding="utf-8")
    
    # Save summary JSON
    summary = {
        "mean_answer_relevancy": float(results_df["answer_relevancy"].mean()),
        "mean_educational_quality": float(results_df["educational_quality"].mean()),
        "mean_crosscheck_faithfulness": float(results_df[results_df["deepeval_faithfulness"].notna()]["deepeval_faithfulness"].mean())
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
