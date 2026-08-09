# Load .env FIRST before any other imports so os.getenv() works everywhere
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
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

@app.get("/internal/llm-health/{probe_key}")
async def temporary_llm_health(probe_key: str):
    if probe_key != "llm-probe-93fd2b":
        raise HTTPException(status_code=404, detail="Not found")
    from app.ai_system.services.llm.providers.groq_provider import GroqProvider
    try:
        result = await GroqProvider().generate(
            model="openai/gpt-oss-120b",
            prompt="Reply with exactly: LLM_OK",
            temperature=0,
            max_tokens=16,
            api_key="",
            profile="execution_reduce",
        )
        return {
            "ok": True,
            "provider": result.get("provider"),
            "model": result.get("model"),
            "text": result.get("text", "")
        }
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "message": str(exc)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
