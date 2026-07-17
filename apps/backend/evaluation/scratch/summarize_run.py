import sys
import json

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

records = [json.loads(l) for l in open('evaluation/results/raw/pipeline_outputs.jsonl', encoding='utf-8') if l.strip()]

# Get the most recent entry for each of the 30 test cases
last_records = {}
for r in records:
    cid = r['test_case_id']
    last_records[cid] = r

refusal_kw = [
    "لم أجد إجابة", "لا يحتوي الملف", "خارج نطاق",
    "could not find", "cannot find", "does not provide enough",
    "no relevant context", "out of scope",
]

total = len(last_records)
refusals = 0
answered = 0
passed_verifier = 0
failed_verifier = 0

print(f"Total Unique Cases in raw output: {total}")
print("Detailed breakdown:")
print("| ID | Verifier | Refusal? | Top Retrieval Score | Top Reranker Score | Answer Preview |")
print("|---|---|---|---|---|---|")

for cid in sorted(last_records.keys()):
    r = last_records[cid]
    ans = r.get('actual_answer', 'N/A')
    is_refusal = any(kw in ans.lower() or kw in ans for kw in refusal_kw)
    if is_refusal:
        refusals += 1
    else:
        answered += 1
    
    ver = r.get('verifier_status', 'N/A')
    if ver == 'passed':
        passed_verifier += 1
    else:
        failed_verifier += 1
        
    ret_scores = r.get('retrieval_scores', [])
    rerank_scores = r.get('reranker_scores', [])
    top_ret = max(ret_scores) if ret_scores else 0.0
    top_rerank = max(rerank_scores) if rerank_scores else 0.0
    
    print(f"| {cid} | {ver} | {is_refusal} | {top_ret:.4f} | {top_rerank:.4f} | {ans[:60]}... |")

print("\nSummary:")
print(f"Answered: {answered}")
print(f"Refused: {refusals}")
print(f"Verifier Passed: {passed_verifier}")
print(f"Verifier Failed: {failed_verifier}")
