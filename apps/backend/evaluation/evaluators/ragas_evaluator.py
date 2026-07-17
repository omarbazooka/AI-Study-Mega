import os
import sys
import json
import pandas as pd
from typing import List, Dict, Any

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import yaml
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerCorrectness
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.core.config import settings

def load_config() -> Dict[str, Any]:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "evaluation.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_ragas_evaluation():
    print("[RAGAS] Starting RAGAS evaluation...")
    
    config = load_config()
    
    # Load raw outputs
    raw_outputs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["raw_outputs"]))
    if not os.path.exists(raw_outputs_path):
        print(f"[RAGAS] ERROR: Raw outputs file '{raw_outputs_path}' not found. Run pipeline evaluation first.")
        sys.exit(1)
        
    records = []
    with open(raw_outputs_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
                
    # Load golden dataset to get reference answers
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["dataset_jsonl"]))
    golden_cases = {}
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                golden_cases[case["test_case_id"]] = case
                
    # Map data
    evaluation_data = []
    for r in records:
        case_id = r["test_case_id"]
        golden = golden_cases.get(case_id)
        if not golden:
            continue
            
        # Handle unanswerable questions reference answer (null/fallback)
        ref_ans = golden.get("reference_answer")
        if ref_ans is None:
            ref_ans = "لم أجد إجابة واضحة في الملف المرفوع." if golden["language"] == "ar" else "I couldn't find a clear answer in the uploaded document."
            
        evaluation_data.append({
            "test_case_id": case_id,
            "question": r["question"],
            "user_input": r["question"],
            "answer": r["actual_answer"],
            "response": r["actual_answer"],
            "contexts": r["retrieved_contexts"] if r["retrieved_contexts"] else [""],
            "retrieved_contexts": r["retrieved_contexts"] if r["retrieved_contexts"] else [""],
            "ground_truth": ref_ans,
            "reference": ref_ans,
            "answerable": golden.get("answerable", True)
        })
        
    if not evaluation_data:
        print("[RAGAS] WARNING: No evaluation data matched the golden dataset.")
        return
    # Configure LLM Judge model name
    judge_model = config["judge"].get("model", "llama-3.3-70b-versatile")

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

    df = pd.DataFrame(evaluation_data)
    
    # Partition dataset: cases to evaluate via RAGAS vs cases scored directly
    eval_mask = df.apply(lambda row: row["answerable"] and not is_refusal_answer(row["answer"]), axis=1)
    df_eval = df[eval_mask].copy()
    df_direct = df[~eval_mask].copy()
    
    results_list = []
    
    if not df_eval.empty:
        # Convert to datasets.Dataset
        dataset = Dataset.from_pandas(df_eval)
        
        # Configure LLM Judge (pointing to project's centralized model router)
        from evaluation.evaluators.centralized_adapters import CentralizedRagasLLM
        from ragas.embeddings import LangchainEmbeddingsWrapper
        
        print(f"[RAGAS] Configuring CentralizedRagasLLM judge using central router ({judge_model})...")
        groq_llm = CentralizedRagasLLM(model_name=judge_model)
        
        # Configure local HuggingFace embeddings
        print("[RAGAS] Configuring local HuggingFaceEmbeddings with LangchainEmbeddingsWrapper...")
        local_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        wrapped_embeddings = LangchainEmbeddingsWrapper(local_embeddings)
        
        # Instantiate metric objects
        faithfulness_metric = Faithfulness(llm=groq_llm)
        answer_correctness_metric = AnswerCorrectness(llm=groq_llm, embeddings=wrapped_embeddings)
        
        metrics = [faithfulness_metric, answer_correctness_metric]
        
        print(f"[RAGAS] Running RAGAS evaluate on {len(df_eval)} cases with RunConfig(max_workers=1)...")
        from ragas.run_config import RunConfig
        run_cfg = RunConfig(max_workers=1, timeout=120)
        try:
            result = evaluate(dataset=dataset, metrics=metrics, run_config=run_cfg)
            eval_results = result.to_pandas()
            eval_results["test_case_id"] = df_eval["test_case_id"].values
            eval_results["evaluation_type"] = "framework_evaluated"
            results_list.append(eval_results[["test_case_id", "faithfulness", "answer_correctness", "evaluation_type"]])
        except Exception as e:
            print(f"[RAGAS] ERROR during evaluate execution: {e}")
            # Fallback: mark as error (None) NOT as 0.0 — 0.0 literals distort framework averages
            fallback_df = df_eval[["test_case_id"]].copy()
            fallback_df["faithfulness"] = None
            fallback_df["answer_correctness"] = None
            fallback_df["evaluation_type"] = "framework_error"
            results_list.append(fallback_df)
    else:
        print("[RAGAS] No cases require LLM-based evaluation (all are refusals or unanswerable).")

    if not df_direct.empty:
        direct_results = []
        for _, row in df_direct.iterrows():
            ans = row["answer"]
            ans_refusal = is_refusal_answer(ans)
            
            if not row["answerable"]:
                # Unanswerable case
                if ans_refusal:
                    # Correct refusal
                    faith = 1.0
                    corr = 1.0
                else:
                    # Hallucination
                    faith = 0.0
                    corr = 0.0
            else:
                # Answerable case that got refused (False Refusal)
                faith = None  # Faithful (no claims), but not_applicable for faithfulness metric
                corr = 0.0   # Incorrect: should have answered

            direct_results.append({
                "test_case_id": row["test_case_id"],
                "faithfulness": faith,
                "answer_correctness": corr,
                "evaluation_type": "programmatic",  # NOT framework_evaluated
            })
        results_list.append(pd.DataFrame(direct_results))
        
    # Combine and save results
    results_df = pd.concat(results_list, ignore_index=True)
    
    # Ensure all original cases are included in order
    results_df = df[["test_case_id"]].merge(results_df, on="test_case_id", how="left")
    
    ragas_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["ragas_results_csv"]))
    os.makedirs(os.path.dirname(ragas_csv_path), exist_ok=True)
    results_df.to_csv(ragas_csv_path, index=False, encoding="utf-8")
    
    # Save summary — compute means ONLY over framework_evaluated rows (not programmatic)
    fw_mask = results_df["evaluation_type"] == "framework_evaluated" if "evaluation_type" in results_df.columns else pd.Series([True] * len(results_df))
    df_fw = results_df[fw_mask]

    def safe_mean(series):
        valid = series.dropna()
        return float(valid.mean()) if len(valid) > 0 else None

    summary = {
        "framework_evaluated_count": int(fw_mask.sum()) if "evaluation_type" in results_df.columns else len(results_df),
        "programmatic_count": int((~fw_mask).sum()) if "evaluation_type" in results_df.columns else 0,
        "mean_answer_correctness": safe_mean(df_fw["answer_correctness"]) if not df_fw.empty else None,
        "mean_faithfulness": safe_mean(df_fw["faithfulness"]) if not df_fw.empty else None,
        "failure_count": int(results_df["answer_correctness"].isna().sum() + results_df["faithfulness"].isna().sum()),
        "note": "Means computed only over framework_evaluated cases; programmatic scores excluded from framework averages.",
    }
    
    ragas_summary_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["ragas_summary_json"]))
    with open(ragas_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    # Save metadata
    metadata = {
        "judge_model": judge_model,
        "judge_provider": "groq",
        "ragas_version": "0.4.3",
        "evaluation_timestamp": pd.Timestamp.now().isoformat(),
        "metrics_run": ["answer_correctness", "faithfulness"]
    }
    
    ragas_metadata_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["ragas_metadata_json"]))
    with open(ragas_metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"[RAGAS] SUCCESS: RAGAS evaluation complete!")
    print(f"[RAGAS] Results CSV: {ragas_csv_path}")
    print(f"[RAGAS] Summary JSON: {ragas_summary_path}")


if __name__ == "__main__":
    run_ragas_evaluation()
