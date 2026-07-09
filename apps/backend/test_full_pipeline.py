"""
Full end-to-end test: retrieval + LLM generation.
Tests the exact same path the API uses.
Run: python test_full_pipeline.py
"""
import asyncio, os
from dotenv import load_dotenv
load_dotenv(".env")

DOCUMENT_ID  = "12d9c374-70fb-472f-a5b0-640c1da59b66"  # MY-CV.pdf
USER_ID      = "00000000-0000-0000-0000-000000000000"
SESSION_ID   = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"  # valid UUID
QUERY        = "i need to know what the title of omar?"

async def main():
    print("=" * 60)
    print("  FULL PIPELINE TEST (Retrieval + LLM)")
    print("=" * 60)

    from app.schemas.ai_schema import PDFChatRequest
    from app.services.ai_orchestrator import ai_orchestrator_service

    request = PDFChatRequest(
        message=QUERY,
        session_id=SESSION_ID,
        user_id=USER_ID,
        language="en",
    )

    print(f"  Document : MY-CV.pdf ({DOCUMENT_ID})")
    print(f"  Query    : {QUERY}\n")

    try:
        response = await ai_orchestrator_service.execute_query(
            document_id=DOCUMENT_ID,
            request=request,
            user_id=USER_ID,
        )
        print(f"Status    : {response.status}")
        print(f"Confidence: {response.confidence}")
        print(f"\nAnswer:\n{response.message}")
        if response.pipeline_trace:
            rt = response.pipeline_trace.get("retrieval", {})
            print(f"\nRetrieval : {rt.get('status')} | chunks={rt.get('chunks_used')} | conf={rt.get('confidence')}")
            vt = response.pipeline_trace.get("orchestrator", {})
            print(f"Verifier  : {vt.get('verifier_status')}")
    except Exception as e:
        import traceback
        print(f"PIPELINE ERROR: {e}")
        # Try to get more detail by running the internal steps manually
        print("\n--- Debugging inner task failure ---")
        from app.ai_system.orchestrator.planner import TaskPlanner
        from app.ai_system.orchestrator.orchestrator import TaskOrchestrator
        from app.ai_system.orchestrator.document_guard import validate_document_access

        request2 = PDFChatRequest(
            message=QUERY, session_id=SESSION_ID,
            user_id=USER_ID, language="en",
        )
        await validate_document_access(DOCUMENT_ID, USER_ID)
        request2.document_id = DOCUMENT_ID
        planner = TaskPlanner()
        plan = planner.plan(request2)
        print(f"Plan tasks: {[t.type.value for t in plan.tasks]}")
        print(f"retrieval_required: {[t.retrieval_required for t in plan.tasks]}")

        orch = TaskOrchestrator()
        completed = {}
        for task in plan.tasks:
            try:
                from app.ai_system.orchestrator.pipeline_registry import PIPELINE_REGISTRY
                fn = PIPELINE_REGISTRY.get(task.type.value)
                result = await fn(task, request2, completed)
                completed[task.task_id] = result
                print(f"\nTask {task.task_id} ({task.type.value}):")
                print(f"  status : {result.status}")
                print(f"  content: {result.content[:200] if result.content else 'EMPTY'}")
                print(f"  error  : {result.error}")
                print(f"  meta   : {result.metadata}")
            except Exception as te:
                print(f"  Task exception: {te}")
                traceback.print_exc()

asyncio.run(main())
