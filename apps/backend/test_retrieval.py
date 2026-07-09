"""
End-to-end retrieval test for a specific document.
Run: python test_retrieval.py
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv(".env")

DOCUMENT_ID = "12d9c374-70fb-472f-a5b0-640c1da59b66"  # MY-CV.pdf
USER_ID = "00000000-0000-0000-0000-000000000000"
QUERY = "i need to know what the title of omar?"

async def main():
    print("=" * 55)
    print("  END-TO-END RETRIEVAL TEST")
    print("=" * 55)
    print(f"  Document: MY-CV.pdf ({DOCUMENT_ID})")
    print(f"  Query   : {QUERY}")
    print()

    # Step 1: Check chunks exist in DB
    from supabase import create_client

    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    print("[1] Checking chunks in Supabase...")
    try:
        resp = client.table("chunks").select("id, chunk_index, text").eq("document_id", DOCUMENT_ID).limit(5).execute()
        chunks = resp.data
        if chunks:
            print(f"    Found {len(chunks)} chunks (showing first 3):")
            for c in chunks[:3]:
                print(f"    [{c['chunk_index']}] {c['text'][:80]}...")
        else:
            print("    NO CHUNKS FOUND in Supabase!")
            print("    The document was NOT properly embedded.")
    except Exception as e:
        print(f"    DB error: {e}")

    print()

    # Step 2: Test query rewriter
    print("[2] Testing Query Rewriter...")
    from app.ai_system.retrieval.query_rewriter import QueryRewriter
    rewriter = QueryRewriter()
    result = rewriter.rewrite(QUERY, intent="chat_answer")
    print(f"    Keywords     : {result.keywords}")
    print(f"    Semantic Q   : {result.semantic_query}")
    print(f"    Keyword Q    : {result.keyword_query}")
    print(f"    Filters      : {result.filters}")
    has_filter = result.filters.as_repository_filter() if hasattr(result.filters, 'as_repository_filter') else {}
    print(f"    Filter active: {has_filter}")
    if not result.keywords and not has_filter:
        print("    WARNING: No keywords + no filter = NEEDS_CLARIFICATION triggered!")

    print()

    # Step 3: Full retrieval
    print("[3] Running Full Retrieval Pipeline...")
    from app.ai_system.retrieval import get_document_retriever
    from app.ai_system.retrieval.schemas import RetrievalRequest, RetrievalStatus

    retriever = get_document_retriever()
    req = RetrievalRequest(
        user_id=USER_ID,
        document_id=DOCUMENT_ID,
        query=QUERY,
        intent="chat_answer",
    )
    try:
        retrieval_result = await retriever.retrieve(req)
        print(f"    Status   : {retrieval_result.status}")
        print(f"    Reason   : {retrieval_result.reason}")
        print(f"    Chunks   : {len(retrieval_result.chunks)}")
        print(f"    Confidence: {retrieval_result.confidence}")
        if retrieval_result.chunks:
            print(f"    Top chunk: {retrieval_result.chunks[0].text[:100]}...")
        if retrieval_result.trace:
            t = retrieval_result.trace
            print(f"    Vector results  : {t.vector_results}")
            print(f"    Keyword results : {t.keyword_results}")
            print(f"    Candidates      : {t.hybrid_candidates}")
            print(f"    Final selected  : {t.final_selected}")
    except Exception as e:
        import traceback
        print(f"    RETRIEVAL ERROR: {e}")
        traceback.print_exc()

asyncio.run(main())
