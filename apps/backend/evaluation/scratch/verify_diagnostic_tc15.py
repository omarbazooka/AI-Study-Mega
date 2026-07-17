import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db.supabase_client import get_supabase_client
from app.ai_system.validation.verifier import verify_response
from app.ai_system.validation.schemas import RetrievedChunk, TaskType, ResponseStrategy, DocumentTaskType

async def main():
    # Let's mock a simple verification run for TC-015
    user_query = "How does the training phase of a foundation model use large-scale raw data and fill‑in‑the‑blank tasks to continuously reduce the gap between its predictions and the actual data?"
    task_type = TaskType.CHAT
    
    # Retrieved chunks
    chunks = [
        RetrievedChunk(
            chunk_id="a59ae8a1-20d6-4527-b916-5c247b417107",
            text="Training Phase\n• To create a foundation model, practitioners train a deep\nlearning algorithm on huge volumes of raw, unstructured,\nunlabeled data e.g., terabytes of data from the internet\nor some other huge data source.\n• During training, the algorithm performs and evaluates\nmillions of ‘fill in the blank’ exercises, trying to predict\nthe next element in a sequence e.g., the next word in a\nsentence, the next element in an image, the next\ncommand in a line of code and continually adjusting itself\nto minimize the difference between its predictions and\nthe actual data.\n7\nاو الفرق بين المتوقع والحقيقي ونحاول نقلل الرقم ده علطول بشكل دوريErrorبنحاول نقلل",
            page_number=7,
            section_title="Training Phase",
            similarity_score=0.641308
        )
    ]
    
    executor_output = "لم أجد إجابة واضحة في الملف المرفوع."
    
    res = await verify_response(
        user_query=user_query,
        task_type=task_type,
        retrieved_chunks=chunks,
        executor_output=executor_output,
        response_strategy=ResponseStrategy.generate_partial_evidence_response,
        primary_task=DocumentTaskType.document_factual_qa
    )
    
    print("Passed:", res.passed)
    print("Action:", res.action)
    print("Reasons:", res.reasons)
    print("Final answer:", res.final_answer)

if __name__ == "__main__":
    asyncio.run(main())
