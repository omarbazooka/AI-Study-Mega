import os
import sys
import json
import asyncio
import uuid
import time
from typing import List

# Setup path
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BACKEND)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

os.environ["EVALUATION_RUN"] = "true"

from app.core.config import settings
from app.schemas.ai_schema import PDFChatRequest
from app.services.ai_orchestrator import AIOrchestratorService
from evaluation.runners.auth_helper import authenticate_evaluation_user

DEV_CASE_IDS = ["TC-023", "TC-001", "TC-004", "TC-006", "TC-008", "TC-010"]
GOLDEN_PATH = os.path.join(BACKEND, "evaluation", "datasets", "golden_dataset.jsonl")

async def run_benchmark():
    print("=== STARTING SIX-CASE DEVELOPMENT BENCHMARK ===")
    
    # 1. Authenticate user
    try:
        user_id, access_token = authenticate_evaluation_user()
        from app.db.supabase_client import get_supabase_client
        get_supabase_client().postgrest.auth(access_token)
        print(f"[BENCHMARK] Authenticated as user: {user_id}")
    except Exception as e:
        print(f"[BENCHMARK] Auth failed: {e}")
        return
        
    # 2. Load the 6 cases
    cases = []
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                if c["test_case_id"] in DEV_CASE_IDS:
                    cases.append(c)
                    
    # Sort to match order of DEV_CASE_IDS
    cases.sort(key=lambda x: DEV_CASE_IDS.index(x["test_case_id"]))
    
    orchestrator = AIOrchestratorService()
    
    passed_all = True
    results = []
    
    for case in cases:
        cid = case["test_case_id"]
        q = case["question"]
        doc_id = case["document_id"]
        lang = case["language"]
        is_answerable = case.get("answerable", True)
        
        print(f"\nRunning {cid} ({lang}): '{q[:60]}...'")
        
        req = PDFChatRequest(
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            message=q,
            language=lang,
            user_level=case.get("difficulty", "intermediate"),
            request_source="chat",
            document_id=doc_id
        )
        
        start = time.perf_counter()
        response = None
        error_msg = None
        
        try:
            # We execute it fresh (force execution, bypassing any cache in orchestrator if applicable)
            response = await orchestrator.execute_query(doc_id, req, user_id)
        except Exception as e:
            error_msg = str(e)
            
        latency = time.perf_counter() - start
        
        # Check result conditions
        has_tech_failure = error_msg is not None
        actual_ans = response.message if response else ""
        
        refusal_keywords = [
            "لم أجد إجابة", "لا يحتوي الملف", "لا يوجد", "خارج نطاق",
            "does not provide enough supporting evidence",
            "couldn't find details supporting",
            "could not find", "cannot find", "unable to find",
            "no relevant context", "out of scope",
            "does not contain information"
        ]
        is_fallback = any(kw in actual_ans.lower() for kw in refusal_keywords)
        
        status = "PASSED"
        reasons = []
        
        if has_tech_failure:
            status = "FAILED"
            reasons.append(f"Technical failure: {error_msg}")
            passed_all = False
        else:
            # Check answer correctness / fallback logic
            if is_answerable:
                if is_fallback:
                    status = "FAILED"
                    reasons.append("False refusal: system returned fallback on answerable case.")
                    passed_all = False
                elif not response.citations:
                    status = "FAILED"
                    reasons.append("Missing citations for substantive answer.")
                    passed_all = False
            else:
                if not is_fallback:
                    status = "FAILED"
                    reasons.append("Failed to fallback on unanswerable case.")
                    passed_all = False
                    
        print(f"  Result: {status} | Latency: {latency:.2f}s")
        if reasons:
            for r in reasons:
                print(f"    - {r}")
                
        results.append({
            "test_case_id": cid,
            "status": status,
            "latency": latency,
            "reasons": reasons
        })
        
        # Pace requests to avoid Groq TPM limits
        await asyncio.sleep(12)
        
    print("\n=== BENCHMARK SUMMARY ===")
    all_ok = True
    for r in results:
        print(f"Case {r['test_case_id']}: {r['status']} ({r['latency']:.2f}s)")
        if r["status"] == "FAILED":
            all_ok = False
            
    if all_ok:
        print("SUCCESS: All 6 development cases passed benchmark criteria!")
    else:
        print("WARNING: Some development benchmark cases failed.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
