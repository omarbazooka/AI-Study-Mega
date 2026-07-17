import os
import sys
import json
import hashlib
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Run without display server
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any

# Reconfigure stdout/stderr to utf-8 to prevent CP1252 errors on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import yaml

def load_config() -> Dict[str, Any]:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "evaluation.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_file_hash(path: str) -> str:
    if not os.path.exists(path):
        return "not_found"
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def write_metadata(chart_path: str, source_files: list, samples_used: int, samples_excluded: int):
    metadata_path = chart_path + ".metadata.json"
    sources_info = {}
    for fpath in source_files:
        if os.path.exists(fpath):
            sources_info[os.path.basename(fpath)] = {
                "path": fpath,
                "sha256": get_file_hash(fpath)
            }
    
    metadata = {
        "chart_name": os.path.basename(chart_path),
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_files": sources_info,
        "samples_used": int(samples_used),
        "samples_excluded": int(samples_excluded)
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

def generate_charts():
    print("[CHARTS] Starting chart generation...")
    config = load_config()
    
    # Paths
    local_results_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["local_results_json"]))
    raw_outputs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["raw_outputs"]))
    ragas_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["ragas_results_csv"]))
    deepeval_csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["deepeval_results_csv"]))
    
    charts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["charts_dir"]))
    os.makedirs(charts_dir, exist_ok=True)
    
    # Check that result files exist
    if not os.path.exists(local_results_path) or not os.path.exists(raw_outputs_path):
        print(f"[CHARTS] ERROR: Result files not found. Run evaluation and metric calculations first.")
        sys.exit(1)
        
    # Load JSON files
    with open(local_results_path, "r", encoding="utf-8") as f:
        local_metrics = json.load(f)
        
    records = []
    with open(raw_outputs_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
                
    df_raw = pd.DataFrame(records)
    
    # Load golden dataset for categories/filenames
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["dataset_jsonl"]))
    golden_records = []
    if os.path.exists(dataset_path):
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    golden_records.append(json.loads(line))
    df_golden = pd.DataFrame(golden_records)[["test_case_id", "category", "document_filename", "answerable"]]
    
    # Ensure raw latency stages exist, default to NaN (null) if missing
    for col in ["planning_latency_ms", "retrieval_latency_ms", "reranking_latency_ms", "generation_latency_ms", "verification_latency_ms"]:
        if col not in df_raw.columns:
            df_raw[col] = np.nan
            
    df_ragas = pd.read_csv(ragas_csv_path) if os.path.exists(ragas_csv_path) else pd.DataFrame(columns=["test_case_id", "answer_correctness", "faithfulness"])
    df_deepeval = pd.read_csv(deepeval_csv_path) if os.path.exists(deepeval_csv_path) else pd.DataFrame(columns=["test_case_id", "answer_relevancy", "educational_quality"])
    
    # Merge datasets for joint visualizations
    df_master = df_raw.merge(df_golden, on="test_case_id", how="left")
    df_master = df_master.merge(df_ragas, on="test_case_id", how="left")
    df_master = df_master.merge(df_deepeval, on="test_case_id", how="left")
    
    source_files = [local_results_path, raw_outputs_path, ragas_csv_path, deepeval_csv_path]
    
    # Set plot style
    sns.set_theme(style="whitegrid")
    plt.rcParams["figure.dpi"] = 300
    
    # Helper to count NaN exclusions
    def get_valid_counts(df, columns):
        valid = df[columns].dropna()
        used = len(valid)
        excl = len(df) - used
        return used, excl
    
    # 1. AI Quality Radar Chart
    print("[CHARTS] 1. AI Quality Radar Chart")
    radar_cols = ["answer_correctness", "faithfulness", "answer_relevancy", "educational_quality"]
    # Add precision and recall placeholders from local metrics
    avg_prec = local_metrics["retrieval"].get("precision_at_5", 0.0)
    avg_rec = local_metrics["retrieval"].get("recall_at_5", 0.0)
    
    mean_corr = df_master["answer_correctness"].dropna().mean() if "answer_correctness" in df_master.columns else 0.0
    mean_faith = df_master["faithfulness"].dropna().mean() if "faithfulness" in df_master.columns else 0.0
    mean_rel = df_master["answer_relevancy"].dropna().mean() if "answer_relevancy" in df_master.columns else 0.0
    mean_edu = df_master["educational_quality"].dropna().mean() if "educational_quality" in df_master.columns else 0.0
    
    labels = ['Answer Correctness', 'Faithfulness', 'Answer Relevancy', 'Educational Quality', 'Context Precision@5', 'Context Recall@5']
    stats = [mean_corr, mean_faith, mean_rel, mean_edu, avg_prec, avg_rec]
    
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#3B82F6', alpha=0.25)
    ax.plot(angles, stats, color='#1D4ED8', linewidth=2)
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    plt.title("AI Quality Dimension Radar", fontsize=12, fontweight='bold', pad=20)
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "01_ai_quality_radar.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    
    # Calculate samples used for radar (mean of available LLM evals)
    used, excl = get_valid_counts(df_master, ["answer_correctness", "faithfulness", "answer_relevancy"])
    write_metadata(chart_path, source_files, used, excl)
    
    # 2. Overall AI Quality Gauge Chart (Project-Defined)
    print("[CHARTS] 2. Project-Defined Quality Gauge Chart")
    composite_score = local_metrics.get("project_defined_composite_score", 0.0)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh(0, composite_score, color='#10B981', height=0.4, label='Measured Score')
    ax.barh(0, 1.0 - composite_score, left=composite_score, color='#E5E7EB', height=0.4)
    ax.axvline(0.80, color='#EF4444', linestyle='--', linewidth=1.5, label='Acceptance Threshold (0.80)')
    ax.set_xlim(0, 1.0)
    ax.set_yticks([])
    ax.set_xlabel("Score")
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.6), ncol=2, frameon=False, fontsize=8)
    plt.title(f"Project-Defined AI Quality Composite: {composite_score:.4f}", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "02_quality_gauge.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [local_results_path], len(df_master), 0)
    
    # 3. Latency Distribution Histogram
    print("[CHARTS] 3. Latency Distribution Histogram")
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(df_master["total_latency_ms"].dropna(), bins=10, kde=True, color='#6366F1', ax=ax)
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Count")
    plt.title("End-to-End Response Latency Distribution", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "03_latency_histogram.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    used, excl = get_valid_counts(df_master, ["total_latency_ms"])
    write_metadata(chart_path, [raw_outputs_path], used, excl)
    
    # 4. Stage Latency Bar Chart
    print("[CHARTS] 4. Stage Latency Bar Chart")
    stages = ['Planning', 'Retrieval', 'Reranking', 'Generation', 'Verification']
    stage_means = [
        df_master["planning_latency_ms"].dropna().mean() if "planning_latency_ms" in df_master.columns else 0.0,
        df_master["retrieval_latency_ms"].dropna().mean() if "retrieval_latency_ms" in df_master.columns else 0.0,
        df_master["reranking_latency_ms"].dropna().mean() if "reranking_latency_ms" in df_master.columns else 0.0,
        df_master["generation_latency_ms"].dropna().mean() if "generation_latency_ms" in df_master.columns else 0.0,
        df_master["verification_latency_ms"].dropna().mean() if "verification_latency_ms" in df_master.columns else 0.0
    ]
    # Filter out NaNs for plot
    stages_clean = []
    means_clean = []
    for s, m in zip(stages, stage_means):
        if not pd.isna(m):
            stages_clean.append(s)
            means_clean.append(m)
            
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.barplot(x=stages_clean, y=means_clean, palette='viridis', ax=ax)
    ax.set_ylabel("Mean Latency (ms)")
    plt.title("Average Execution Stage Latency Breakdown", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "04_stage_latency_bar.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [raw_outputs_path], len(df_master), 0)
    
    # 5. Latency Box Plot (by category)
    print("[CHARTS] 5. Latency Box Plot")
    fig, ax = plt.subplots(figsize=(7, 4))
    df_box = df_master[["category", "total_latency_ms"]].dropna()
    sns.boxplot(x="category", y="total_latency_ms", data=df_box, palette='Set2', ax=ax)
    ax.set_xlabel("Question Category")
    ax.set_ylabel("Latency (ms)")
    plt.xticks(rotation=15, fontsize=8)
    plt.title("Response Latency by Question Category", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "05_latency_boxplot.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [raw_outputs_path], len(df_box), len(df_master) - len(df_box))
    
    # 6. Metric Distribution Chart
    print("[CHARTS] 6. Metric Distribution Chart")
    fig, ax = plt.subplots(figsize=(6, 4))
    metrics_df = df_master[["answer_correctness", "faithfulness", "answer_relevancy", "educational_quality"]].dropna(how="all")
    metrics_df.columns = ["Correctness", "Faithfulness", "Relevancy", "Edu Quality"]
    
    if not metrics_df.empty:
        sns.boxplot(data=metrics_df, palette='pastel', ax=ax)
    else:
        ax.text(0.5, 0.5, "No evaluators data available", ha='center', va='center')
        
    ax.set_ylabel("Score")
    plt.title("Framework Evaluation Metrics Distribution", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "06_metric_distribution.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [ragas_csv_path, deepeval_csv_path], len(metrics_df), len(df_master) - len(metrics_df))
    
    # 7. Per-Document Grouped Bar Chart
    print("[CHARTS] 7. Per-Document Grouped Bar Chart")
    if "document_filename" in df_master.columns:
        doc_col = "document_filename"
    elif "document_id" in df_master.columns:
        doc_col = "document_id"
    else:
        df_master["document_filename"] = "document_1.pdf"
        doc_col = "document_filename"
        
    doc_grouped = df_master.groupby(doc_col)[["answer_correctness", "faithfulness", "answer_relevancy"]].mean().reset_index()
    
    x = np.arange(len(doc_grouped))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - width, doc_grouped["answer_correctness"].fillna(0.0), width, label='Answer Correctness', color='#3B82F6')
    ax.bar(x, doc_grouped["faithfulness"].fillna(0.0), width, label='Faithfulness', color='#10B981')
    ax.bar(x + width, doc_grouped["answer_relevancy"].fillna(0.0), width, label='Answer Relevancy', color='#F59E0B')
    
    clean_labels = [str(d).replace(".pdf", "") for d in doc_grouped[doc_col]]
    ax.set_xticks(x)
    ax.set_xticklabels(clean_labels, rotation=10, fontsize=8)
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1.1)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.25), ncol=3, frameon=False, fontsize=8)
    plt.title("AI Quality Metrics across Evaluation PDFs", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "07_document_grouped_bar.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, source_files, len(df_master), 0)
    
    # 8. Per-Category Heatmap
    print("[CHARTS] 8. Per-Category Heatmap")
    categories = ['direct_factual', 'explanation', 'multi_chunk', 'comparison', 'summary', 'unanswerable']
    
    cat_grouped = df_master.groupby("category")[["answer_correctness", "faithfulness", "answer_relevancy", "educational_quality", "total_latency_ms"]].mean()
    
    for cat in categories:
        if cat not in cat_grouped.index:
            cat_grouped.loc[cat] = np.nan
            
    cat_grouped = cat_grouped.reindex(categories)
    cat_grouped.columns = ['Correctness', 'Faithfulness', 'Relevancy', 'Edu Quality', 'Latency']
    
    heatmap_norm = cat_grouped.copy()
    max_lat = cat_grouped['Latency'].max()
    if pd.notna(max_lat) and max_lat > 0:
        heatmap_norm['Latency'] = heatmap_norm['Latency'] / max_lat
        
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.heatmap(heatmap_norm.fillna(0.0), annot=cat_grouped.fillna(0.0), fmt=".2f", cmap="YlGnBu", cbar=False, ax=ax)
    plt.title("Performance Heatmap by Question Category", fontsize=11, fontweight='bold', pad=15)
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "08_category_heatmap.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, source_files, len(df_master), 0)
    
    # 9. RAGAS vs DeepEval Comparison Chart
    print("[CHARTS] 9. RAGAS vs DeepEval Comparison Chart")
    fig, ax = plt.subplots(figsize=(6, 4))
    comparison_df = df_master[["answer_correctness", "answer_relevancy"]].dropna()
    
    if not comparison_df.empty:
        sns.scatterplot(x="answer_correctness", y="answer_relevancy", data=comparison_df, color='#EC4899', s=100, ax=ax)
    else:
        ax.text(0.5, 0.5, "No overlapping correctness/relevancy data available", ha='center', va='center')
        
    ax.plot([0.0, 1.0], [0.0, 1.0], color='gray', linestyle='--', linewidth=1)
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("RAGAS Answer Correctness")
    ax.set_ylabel("DeepEval Answer Relevancy")
    plt.title("RAGAS Answer Correctness vs DeepEval Answer Relevancy", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "09_ragas_vs_deepeval.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [ragas_csv_path, deepeval_csv_path], len(comparison_df), len(df_master) - len(comparison_df))
    
    # 10. Correct vs Incorrect Outcome Chart
    print("[CHARTS] 10. Correct vs Incorrect Outcome Chart")
    outcomes = local_metrics.get("outcomes", {"correct_answer": 0, "incorrect_answer": 0, "correct_fallback": 0, "hallucinated_answer": 0})
    outcome_labels = ['Correct Answer', 'Incorrect Answer', 'Correct Fallback', 'Hallucinated Answer']
    outcome_vals = [outcomes.get("correct_answer", 0), outcomes.get("incorrect_answer", 0), outcomes.get("correct_fallback", 0), outcomes.get("hallucinated_answer", 0)]
    
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.barplot(x=outcome_labels, y=outcome_vals, palette='coolwarm', ax=ax)
    ax.set_ylabel("Count")
    plt.title(f"Distribution of Pipeline Output Outcomes (n = {sum(outcome_vals)})", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "10_outcomes_bar.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [local_results_path], len(df_master), 0)
    
    # 11. Answerability Confusion Matrix
    print("[CHARTS] 11. Answerability Confusion Matrix")
    matrix = local_metrics.get("confusion_matrix", {"true_answer": 0, "false_refusal": 0, "hallucinated_answer": 0, "correct_fallback": 0})
    cm_data = np.array([
        [matrix.get("true_answer", 0), matrix.get("false_refusal", 0)],
        [matrix.get("hallucinated_answer", 0), matrix.get("correct_fallback", 0)]
    ])
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(cm_data, annot=True, fmt="d", cmap="Blues", 
                xticklabels=['Answered', 'Refused/Fell back'],
                yticklabels=['Source Answerable', 'Source Unanswerable'], cbar=False, ax=ax)
    plt.title("Answerability Confusion Matrix", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "11_confusion_matrix.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [local_results_path], len(df_master), 0)
    
    # 12. Latency vs Correctness Scatter Plot
    print("[CHARTS] 12. Latency vs Correctness Scatter Plot")
    fig, ax = plt.subplots(figsize=(6, 4))
    scatter_df = df_master[["answer_correctness", "total_latency_ms"]].dropna()
    
    if not scatter_df.empty:
        sns.scatterplot(x="answer_correctness", y="total_latency_ms", data=scatter_df, color='#8B5CF6', s=80, ax=ax)
    else:
        ax.text(0.5, 0.5, "No correctness data available", ha='center', va='center')
        
    ax.set_xlabel("Answer Correctness Score")
    ax.set_ylabel("Total Latency (ms)")
    plt.title("Latency vs Answer Correctness Score", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "12_latency_vs_correctness.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [ragas_csv_path, raw_outputs_path], len(scatter_df), len(df_master) - len(scatter_df))
    
    # 13. Retrieval Quality Chart
    print("[CHARTS] 13. Retrieval Quality Chart")
    ret_labels = ['Precision@3', 'Precision@5', 'Recall@3', 'Recall@5', 'Citation Chunk Acc']
    ret_vals = [
        local_metrics["retrieval"].get("precision_at_3", 0.0),
        local_metrics["retrieval"].get("precision_at_5", 0.0),
        local_metrics["retrieval"].get("recall_at_3", 0.0),
        local_metrics["retrieval"].get("recall_at_5", 0.0),
        local_metrics["citation"].get("chunk_accuracy", 0.0)
    ]
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.barplot(x=ret_labels, y=ret_vals, palette='crest', ax=ax)
    ax.set_ylabel("Percentage")
    ax.set_ylim(0, 1.1)
    plt.title("Retrieval Performance & Citation Accuracy", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "13_retrieval_quality.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [local_results_path], len(df_master), 0)
    
    # 14. Token Usage Chart (Placeholder)
    print("[CHARTS] 14. Token Usage Chart")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, "Token Usage Data Unavailable\n(Skipped to prevent fabrication)", 
            ha='center', va='center', fontsize=10, color='gray')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    plt.title("Token Usage Breakdown", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "14_token_usage.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [], 0, 0)
    
    # 15. Framework Agreement Chart
    print("[CHARTS] 15. Framework Agreement Chart")
    agreement = local_metrics["framework_agreement"].get("agreement_rate", 0.0)
    mean_diff = local_metrics["framework_agreement"].get("mean_score_difference", 0.0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(['Pass/Fail Agreement %', 'Mean Score Difference'], [agreement * 100, mean_diff * 100], color=['#F43F5E', '#10B981'], width=0.4)
    ax.set_ylabel("Percentage (%)")
    ax.set_ylim(0, 110)
    plt.title("RAGAS and DeepEval Cross-Framework Agreement", fontsize=11, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "15_framework_agreement.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    write_metadata(chart_path, [local_results_path], len(df_master), 0)
    
    print(f"[CHARTS] SUCCESS: All 15 charts and metadata files generated in: {charts_dir}")

if __name__ == "__main__":
    generate_charts()
