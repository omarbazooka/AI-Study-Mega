import os
import sys
import json
import time
import argparse
import asyncio
import uuid
import hashlib
from typing import List, Dict, Any
from unittest.mock import patch

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import yaml
from app.core.config import settings
from app.schemas.ai_schema import PDFChatRequest, ExecutionMode, TaskType
from app.services.ai_orchestrator import AIOrchestratorService
from evaluation.runners.auth_helper import authenticate_evaluation_user

# Global latencies for patching
stage_latencies = {
    "planner_start": 0.0,
    "planner_end": 0.0,
    "retrieval_start": 0.0,
    "retrieval_end": 0.0,
    "generation_start": 0.0,
    "generation_end": 0.0,
    "verification_start": 0.0,
    "verification_end": 0.0,
}

# Wrapper patches to capture stage-level latencies
def timing_wrap_planner(original_method):
    async def wrapper(self, request, *args, **kwargs):
        stage_latencies["planner_start"] = time.perf_counter()
        res = await original_method(self, request, *args, **kwargs)
        stage_latencies["planner_end"] = time.perf_counter()
        return res
    return wrapper

def timing_wrap_collector(original_method):
    async def wrapper(strategy, query, document_id, user_id, request, *args, **kwargs):
        stage_latencies["retrieval_start"] = time.perf_counter()
        res = await original_method(strategy, query, document_id, user_id, request, *args, **kwargs)
        stage_latencies["retrieval_end"] = time.perf_counter()
        return res
    return wrapper

def timing_wrap_generate(original_method):
    async def wrapper(payload, *args, **kwargs):
        stage_latencies["generation_start"] = time.perf_counter()
        res = await original_method(payload, *args, **kwargs)
        stage_latencies["generation_end"] = time.perf_counter()
        return res
    return wrapper

def timing_wrap_verify(original_method):
    async def wrapper(*args, **kwargs):
        stage_latencies["verification_start"] = time.perf_counter()
        res = await original_method(*args, **kwargs)
        stage_latencies["verification_end"] = time.perf_counter()
        return res
    return wrapper

def get_cache_key(doc_hash: str, case_id: str, question: str) -> str:
    """Generates a stable cache key using case characteristics."""
    payload_str = f"{doc_hash}-{case_id}-{question}"
    return hashlib.md5(payload_str.encode("utf-8")).hexdigest()

def load_cache(raw_outputs_path: str) -> Dict[str, Dict[str, Any]]:
    """Loads completed pipeline runs from raw output file."""
    cache = {}
    if os.path.exists(raw_outputs_path):
        print(f"[PIPELINE] Loading existing outputs from {raw_outputs_path} for caching...")
        with open(raw_outputs_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        key = record.get("cache_key") or get_cache_key(
                            record.get("document_hash", ""),
                            record.get("test_case_id", ""),
                            record.get("question", "")
                        )
                        cache[key] = record
                    except Exception as e:
                        print(f"[PIPELINE] Warning: failed to parse cache line: {e}")
        print(f"[PIPELINE] Loaded {len(cache)} cached runs.")
    return cache

def load_config() -> Dict[str, Any]:
    """Loads the evaluation YAML config."""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "evaluation.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

async def run_evaluation():
    parser = argparse.ArgumentParser(description="AI Study Platform Pipeline Evaluation Runner")
    parser.add_argument("--estimate-only", action="store_true", help="Display budget estimation and exit.")
    parser.add_argument("--smoke-test", action="store_true", help="Run 3 representative cases.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of run cases.")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from cache (enabled by default).")
    parser.add_argument("--force", action="store_true", help="Force rerun even if cached.")
    parser.add_argument("--skip-generation", action="store_true", help="Skip dataset generation.")
    parser.add_argument("--skip-ragas", action="store_true", help="Skip RAGAS evaluation.")
    parser.add_argument("--skip-deepeval", action="store_true", help="Skip DeepEval evaluation.")
    parser.add_argument("--report-only", action="store_true", help="Only run charts & reporting stage.")
    
    args, unknown = parser.parse_known_args()
    
    # Load config
    config = load_config()
    raw_outputs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["raw_outputs"]))
    os.makedirs(os.path.dirname(raw_outputs_path), exist_ok=True)
    
    # Load cache
    cache = load_cache(raw_outputs_path)
    
    # Load golden dataset
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", config["paths"]["dataset_jsonl"]))
    if not os.path.exists(dataset_path):
        print(f"[PIPELINE] ERROR: Golden dataset file not found at '{dataset_path}'. Generate it first.")
        sys.exit(1)
        
    cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
                
    # Filter for approved cases only (enforce golden review gate)
    approved_cases = [c for c in cases if c.get("review_status") == "approved"]
    
    # Estimate mode
    if args.estimate_only:
        print("\n=== EVALUATION ESTIMATION REPORT ===")
        print(f"Total test cases in dataset: {len(cases)}")
        print(f"Approved cases: {len(approved_cases)}")
        print(f"Pending/Rejected cases: {len(cases) - len(approved_cases)}")
        
        # Calculate cached completed cases
        cached_count = 0
        for c in approved_cases:
            key = get_cache_key(c["document_hash"], c["test_case_id"], c["question"])
            if key in cache:
                cached_count += 1
                
        print(f"Cached (already completed) runs: {cached_count}")
        print(f"Remaining runs to execute: {len(approved_cases) - cached_count}")
        print(f"Available Centralized LLM Provider: {settings.GROQ_PRIMARY_MODEL} (Groq)")
        print(f"Available Judge Provider: {config['judge']['provider']} (Model: {config['judge']['model']})")
        print("Estimated execution stages:")
        print("  1. Smoke Test (3 cases)")
        print("  2. Full Pipeline execution once per remaining case")
        print("  3. RAGAS Evaluation (Answer Correctness, Faithfulness)")
        print("  4. DeepEval Evaluation (Answer Relevancy, G-Eval Answer Quality)")
        print("  5. Deterministic Metrics & Visualizations")
        print("  6. Comprehensive Report Compilation")
        print("====================================")
        return
        
    if not approved_cases:
        print("[PIPELINE] ERROR: No approved cases found. Review status must be 'approved' to execute the run.")
        print("[PIPELINE] Use: python evaluation/runners/approve_dataset.py to approve candidate cases first.")
        sys.exit(1)
        
    if args.report_only:
        print("[PIPELINE] Report-only mode selected. Skipping pipeline runs.")
        return
        
    # Check budget limits
    max_cases = config["budget"]["max_pipeline_cases"]
    if len(approved_cases) > max_cases:
        print(f"[PIPELINE] WARNING: Approved cases count {len(approved_cases)} exceeds maximum allowed {max_cases}.")
        if config["budget"]["abort_on_budget_exceeded"]:
            print("[PIPELINE] Aborting run due to budget constraint.")
            sys.exit(1)
        approved_cases = approved_cases[:max_cases]
        
    # Select cases for execution
    run_cases = approved_cases
    if args.smoke_test:
        print("[PIPELINE] Smoke-test mode: selecting 3 representative cases (Direct factual, Multi-chunk, Unanswerable)")
        factual_case = next((c for c in approved_cases if c["category"] == "direct_factual"), None)
        multi_case = next((c for c in approved_cases if c["category"] == "multi_chunk"), None)
        unans_case = next((c for c in approved_cases if c["category"] == "unanswerable"), None)
        run_cases = [c for c in [factual_case, multi_case, unans_case] if c is not None]
        if len(run_cases) < 3:
            run_cases = approved_cases[:3]
            
    if args.limit:
        run_cases = run_cases[:args.limit]
        
    print(f"[PIPELINE] Authenticating evaluation user...")
    try:
        user_id, access_token = authenticate_evaluation_user()
    except Exception as e:
        print(f"[PIPELINE] ERROR: Authentication failed: {e}")
        sys.exit(1)
        
    # Instantiate service
    orchestrator_service = AIOrchestratorService()
    
    # Timing Wrappers setup
    from app.ai_system.orchestrator.planner import TaskPlanner
    from app.ai_system.validation.context_collector import collect_context
    from app.ai_system.services.llm.generate import generate as original_generate
    from app.ai_system.validation.verifier import verify_response
    
    TaskPlanner.plan = timing_wrap_planner(TaskPlanner.plan)
    # Note: collect_context is imported directly in pipeline_registry, but we patch it globally
    import app.ai_system.validation.context_collector
    app.ai_system.validation.context_collector.collect_context = timing_wrap_collector(app.ai_system.validation.context_collector.collect_context)
    import app.ai_system.services.llm.generate
    app.ai_system.services.llm.generate.generate = timing_wrap_generate
    import app.ai_system.validation.verifier
    app.ai_system.validation.verifier.verify_response = timing_wrap_verify
    
    # Execution Loop
    print(f"\n[PIPELINE] Starting execution of {len(run_cases)} cases...")
    completed_count = 0
    
    for case in run_cases:
        case_id = case["test_case_id"]
        q = case["question"]
        doc_id = case["document_id"]
        doc_hash = case["document_hash"]
        lang = case["language"]
        
        cache_key = get_cache_key(doc_hash, case_id, q)
        
        # Check cache
        if cache_key in cache and args.resume and not args.force:
            print(f"[PIPELINE] Cache hit for {case_id}: skipping.")
            completed_count += 1
            continue
            
        print(f"\n[PIPELINE] [{completed_count+1}/{len(run_cases)}] Running {case_id}: '{q[:50]}...'")
        
        # Build Request
        session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"session-{case_id}"))
        
        # Reset stage latencies
        for k in stage_latencies:
            stage_latencies[k] = 0.0
            
        request = PDFChatRequest(
            user_id=user_id,
            session_id=session_id,
            message=q,
            language=lang,
            user_level=case.get("difficulty", "intermediate"),
            request_source="chat",
            document_id=doc_id
        )
        
        # Measure end-to-end response latency
        start_time = time.perf_counter()
        
        response = None
        error_msg = None
        
        retries = config["budget"]["max_retries_per_case"]
        for attempt in range(retries + 1):
            try:
                # Direct programmatic execution of the production orchestrator
                response = await orchestrator_service.execute_query(doc_id, request, user_id)
                break
            except Exception as e:
                print(f"[PIPELINE] Attempt {attempt+1} failed for {case_id}: {e}")
                if attempt == retries:
                    error_msg = str(e)
                else:
                    await asyncio.sleep(2.0)
                    
        total_latency = int((time.perf_counter() - start_time) * 1000)
        
        # Construct stage latencies
        def get_diff_ms(start_k, end_k):
            if stage_latencies[start_k] > 0 and stage_latencies[end_k] > 0:
                return int((stage_latencies[end_k] - stage_latencies[start_k]) * 1000)
            return 0
            
        planner_lat = get_diff_ms("planner_start", "planner_end")
        ret_lat = get_diff_ms("retrieval_start", "retrieval_end")
        gen_lat = get_diff_ms("generation_start", "generation_end")
        ver_lat = get_diff_ms("verification_start", "verification_end")
        
        # Retrieve context text and chunk ids
        retrieved_contexts = []
        retrieved_chunk_ids = []
        retrieved_page_numbers = []
        planner_intent = "chat_answer"
        exec_mode = "single"
        verifier_status = "passed"
        verifier_action = "pass"
        final_confidence = 1.0
        
        if response:
            actual_answer = response.message
            final_confidence = response.confidence
            exec_mode = response.execution_mode.value if hasattr(response.execution_mode, "value") else str(response.execution_mode)
            
            # Extract citations and contexts
            if response.citations:
                for c in response.citations:
                    retrieved_chunk_ids.append(c.chunk_id)
                    retrieved_page_numbers.append(c.page_number)
                    
            # Fetch retrieved contexts from the pipeline state trace
            state = getattr(request, "_pipeline_state", None)
            if state and state.retrieval_result:
                res_obj = state.retrieval_result
                if hasattr(res_obj, "chunks") and res_obj.chunks:
                    for chunk in res_obj.chunks:
                        retrieved_contexts.append(chunk.content)
                        if chunk.chunk_id not in retrieved_chunk_ids:
                            retrieved_chunk_ids.append(chunk.chunk_id)
                        if chunk.page_number and chunk.page_number not in retrieved_page_numbers:
                            retrieved_page_numbers.append(chunk.page_number)
                            
            # Fetch verifier trace details
            if state and state.trace_stages:
                for stage in state.trace_stages:
                    if stage.get("stage") == "verifier":
                        verifier_status = "passed" if stage.get("passed") else "failed"
                    if stage.get("stage") == "planner":
                        planner_intent = stage.get("intent", "chat_answer")
        else:
            actual_answer = settings.GROQ_FIRST_FALLBACK_MODEL
            verifier_status = "failed"
            verifier_action = "none"
            
        # Format output
        output_record = {
            "cache_key": cache_key,
            "test_case_id": case_id,
            "question": q,
            "actual_answer": actual_answer,
            "retrieved_contexts": retrieved_contexts,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_page_numbers": retrieved_page_numbers,
            "retrieval_scores": [],
            "reranker_scores": [],
            "citations": [c.model_dump() if hasattr(c, "model_dump") else c for c in (response.citations if response else [])],
            "planner_intent": planner_intent,
            "execution_mode": exec_mode,
            "verifier_status": verifier_status,
            "verifier_action": verifier_action,
            "final_confidence": final_confidence,
            "model_provider": "groq",
            "model_name": settings.GROQ_PRIMARY_MODEL,
            "fallback_models_used": [],
            "prompt_version": "v1.0",
            "retrieval_latency_ms": ret_lat,
            "reranking_latency_ms": 0, # Included in retrieval_latency_ms in pipeline
            "planning_latency_ms": planner_lat,
            "generation_latency_ms": gen_lat,
            "verification_latency_ms": ver_lat,
            "total_latency_ms": total_latency,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Save output record immediately (token-efficient caching rule)
        with open(raw_outputs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(output_record, ensure_ascii=False) + "\n")
            
        print(f"[PIPELINE] SUCCESS: TC-{case_id} finished in {total_latency}ms. Verifier: {verifier_status}")
        completed_count += 1
        
        # Concurrency/Rate limit manager sleep
        await asyncio.sleep(0.5)
        
    print(f"\n[PIPELINE] Finished run! Completed {completed_count} cases. Outputs appended to: {raw_outputs_path}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
