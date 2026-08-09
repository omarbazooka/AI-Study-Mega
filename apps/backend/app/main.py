# Load .env FIRST before any other imports so os.getenv() works everywhere
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.documents import router as documents_router
from app.api.v1.ai import router as ai_router
from app.api.v1.sessions import router as sessions_router
from app.core.config import settings

app = FastAPI(
    title="NHA-4-094 AI Study Platform Ingestion API",
    description="Core backend service for uploading, parsing, chunking, and embedding educational PDFs for RAG retrieval.",
    version="1.0.0"
)

cors_origins = [
    origin.strip().strip("'").strip('"').rstrip("/")
    for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "NHA-4-094 Ingestion API is running.",
        "status": "healthy"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
