import pytest
import numpy as np

def calculate_precision_recall(retrieved_ids, ref_ids, k):
    ret_k = retrieved_ids[:k]
    rel_k = [cid for cid in ret_k if cid in ref_ids]
    precision = len(rel_k) / len(ret_k) if ret_k else 0.0
    recall = len(rel_k) / len(ref_ids) if ref_ids else 0.0
    return precision, recall

def calculate_percentile(latencies, percentile):
    return float(np.percentile(latencies, percentile))

def calculate_composite_score(correctness, faithfulness, relevancy, quality, precision, recall):
    return (
        0.25 * correctness +
        0.25 * faithfulness +
        0.15 * relevancy +
        0.15 * quality +
        0.10 * precision +
        0.10 * recall
    )

def test_precision_recall_at_k():
    ref_ids = ["chunk-1", "chunk-2"]
    retrieved_ids = ["chunk-1", "chunk-5", "chunk-2", "chunk-4"]
    
    # Test K=3
    prec_3, rec_3 = calculate_precision_recall(retrieved_ids, ref_ids, 3)
    assert prec_3 == 2/3
    assert rec_3 == 1.0 # Both ref_ids retrieved in top 3
    
    # Test K=1
    prec_1, rec_1 = calculate_precision_recall(retrieved_ids, ref_ids, 1)
    assert prec_1 == 1.0
    assert rec_1 == 0.5

def test_latency_percentiles():
    latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    p50 = calculate_percentile(latencies, 50)
    p90 = calculate_percentile(latencies, 90)
    p95 = calculate_percentile(latencies, 95)
    
    assert p50 == 550.0
    assert p90 == 910.0
    assert abs(p95 - 955.0) < 1e-2

def test_composite_quality_score():
    score = calculate_composite_score(
        correctness=0.8,
        faithfulness=0.9,
        relevancy=0.85,
        quality=0.87,
        precision=0.7,
        recall=0.8
    )
    # 0.25 * 0.8 + 0.25 * 0.9 + 0.15 * 0.85 + 0.15 * 0.87 + 0.10 * 0.7 + 0.10 * 0.8
    # = 0.2 + 0.225 + 0.1275 + 0.1305 + 0.07 + 0.08 = 0.833
    assert abs(score - 0.833) < 1e-5
