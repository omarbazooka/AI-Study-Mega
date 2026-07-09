"""Test retrieval with new threshold for projects query."""
from dotenv import load_dotenv
load_dotenv(".env")
import asyncio

async def test():
    from app.ai_system.retrieval import get_document_retriever
    from app.ai_system.retrieval.schemas import RetrievalRequest

    retriever = get_document_retriever()
    req = RetrievalRequest(
        user_id="00000000-0000-0000-0000-000000000000",
        document_id="12d9c374-70fb-472f-a5b0-640c1da59b66",
        query="what are the projects of omar?",
        intent="chat_answer",
    )
    result = await retriever.retrieve(req)
    print(f"Status : {result.status}")
    print(f"Chunks : {len(result.chunks)}")
    print(f"Confidence: {result.confidence}")
    print()
    for i, c in enumerate(result.chunks):
        text = c.text[:130].replace("\n", " ")
        print(f"[{i+1}] score={c.score:.3f}: {text}")

asyncio.run(test())
