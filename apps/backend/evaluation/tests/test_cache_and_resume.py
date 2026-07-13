import pytest
import hashlib

def get_cache_key(doc_hash: str, case_id: str, question: str) -> str:
    payload_str = f"{doc_hash}-{case_id}-{question}"
    return hashlib.md5(payload_str.encode("utf-8")).hexdigest()

def test_cache_key_stability():
    h1 = get_cache_key("hash-123", "TC-001", "How does hybrid retrieval work?")
    h2 = get_cache_key("hash-123", "TC-001", "How does hybrid retrieval work?")
    h3 = get_cache_key("hash-999", "TC-001", "How does hybrid retrieval work?")
    
    assert h1 == h2
    assert h1 != h3

def test_resume_bypasses_execution():
    # Cache containing pre-evaluated case
    cache = {
        "key-tc1": {"test_case_id": "TC-001", "actual_answer": "Precomputed answer"}
    }
    
    run_cases = [
        {"test_case_id": "TC-001", "question": "Question 1", "document_hash": "hash-1", "cache_key": "key-tc1"},
        {"test_case_id": "TC-002", "question": "Question 2", "document_hash": "hash-1", "cache_key": "key-tc2"}
    ]
    
    executed = []
    
    for case in run_cases:
        key = case["cache_key"]
        if key in cache:
            # Reused cache
            continue
        executed.append(case["test_case_id"])
        
    # TC-001 should be bypassed, TC-002 should execute
    assert len(executed) == 1
    assert executed[0] == "TC-002"
