import asyncio
import os
import sys
import json

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from app.core.config import settings

from app.schemas.ai_schema import PDFChatRequest
from app.services.ai_orchestrator import AIOrchestratorService
from evaluation.runners.auth_helper import authenticate_evaluation_user

async def test_single_case():
    # Load case 1
    # TC-001: "ما هي أنواع الفعالية المذكورة في النص؟"
    # Doc: "Arabic Document 2.pdf"
    
    print("[TEST] Authenticating...")
    user_id, access_token = authenticate_evaluation_user()
    
    # We need a valid document_id from the golden dataset
    dataset_path = "evaluation/datasets/golden_dataset.jsonl"
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    
    case = next(c for c in cases if c["test_case_id"] == "TC-008")
    doc_id = case["document_id"]
    query = case["question"]
    lang = case["language"]
    
    print(f"[TEST] Running single case TC-001: {query}")
    print(f"[TEST] Doc ID: {doc_id}")
    
    import uuid
    session_id = str(uuid.uuid4())
    
    orchestrator = AIOrchestratorService()
    
    request = PDFChatRequest(
        user_id=user_id,
        session_id=session_id,
        message=query,
        language=lang,
        user_level="intermediate",
        request_source="chat",
        document_id=doc_id
    )

    
    # We want to patch or watch validate_evidence
    from app.ai_system.validation.evidence_gate import validate_evidence
    from app.ai_system.validation.context_collector import collect_context
    from app.ai_system.validation.schemas import ExecutionStrategy, DocumentTaskType
    
    # Mock collect_context and validate_evidence wrapper to print scores
    orig_collect = collect_context
    async def collect_context_wrapper(*args, **kwargs):
        chunks = await orig_collect(*args, **kwargs)
        print(f"[TEST] Collected {len(chunks)} chunks.")
        for idx, c in enumerate(chunks):
            print(f"  Chunk {idx}: score={c.similarity_score}, text={c.text[:100]}...")
        return chunks

        
    import app.ai_system.validation.context_collector
    app.ai_system.validation.context_collector.collect_context = collect_context_wrapper
    
    orig_validate = validate_evidence
    async def validate_evidence_wrapper(*args, **kwargs):
        res = await orig_validate(*args, **kwargs)
        print(f"[TEST] Evidence Gate: status={res.status}, top_score={res.top_score}, action={res.next_action}, provider={res.provider}")
        return res

        
    import app.ai_system.validation.evidence_gate
    app.ai_system.validation.evidence_gate.validate_evidence = validate_evidence_wrapper
    
    try:
        response = await orchestrator.execute_query(doc_id, request, user_id)
        print("\n=== RESPONSE ===")
        print(f"Message: {response.message}")
        print(f"Confidence: {response.confidence}")
        print(f"Citations: {len(response.citations)}")
        print(f"Metadata: {json.dumps(response.metadata or {}, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"[TEST] Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_single_case())
