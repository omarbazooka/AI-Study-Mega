from fastapi import FastAPI
from app.api.v1.documents import router as documents_router
from app.api.v1.ai import router as ai_router

# Initialize the FastAPI application
app = FastAPI(
    title="NHA-4-094 AI Study Platform Ingestion API",
    description="Core backend service for uploading, parsing, chunking, and embedding educational PDFs for RAG retrieval.",
    version="1.0.0"
)

# Register API endpoints under prefix /api/v1
app.include_router(documents_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")

@app.get("/")
async def root():
    """
    Health check endpoint.
    """
    return {
        "message": "NHA-4-094 Ingestion API is running.",
        "status": "healthy"
    }

if __name__ == "__main__":
    import uvicorn
    # Starts server at http://localhost:8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
