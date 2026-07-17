import sys
import json

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

records = [json.loads(l) for l in open('evaluation/results/raw/pipeline_outputs.jsonl', encoding='utf-8') if l.strip()]

# Get the most recent entry for each of the smoke test cases
target_ids = {'TC-001', 'TC-006', 'TC-010'}
last_records = {}
for r in records:
    cid = r['test_case_id']
    if cid in target_ids:
        last_records[cid] = r

refusal_kw = [
    "لم أجد إجابة", "لا يحتوي الملف", "خارج نطاق",
    "could not find", "cannot find", "does not provide enough",
    "no relevant context", "out of scope",
]

for cid in ['TC-001', 'TC-006', 'TC-010']:
    r = last_records.get(cid, {})
    ans = r.get('actual_answer', 'N/A')
    is_refusal = any(kw in ans.lower() or kw in ans for kw in refusal_kw)
    ret_scores = r.get('retrieval_scores', [])
    rerank_scores = r.get('reranker_scores', [])
    print(f"=== {cid} ===")
    print(f"  Verifier: {r.get('verifier_status')}")
    print(f"  Is refusal: {is_refusal}")
    print(f"  Retrieval scores: {ret_scores[:3]}")
    print(f"  Reranker scores:  {rerank_scores[:3]}")
    print(f"  Answer (first 200 chars): {ans[:200]}")
    print()
