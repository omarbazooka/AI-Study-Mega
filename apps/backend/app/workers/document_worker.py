import logging
from app.ai_system.ingestion.ingestion_pipeline import process_document

logger = logging.getLogger(__name__)

async def run_document_ingestion(document_id: str) -> None:
    """
    Background worker wrapper for document ingestion.
    Invokes the linear ingestion pipeline.
    """
    print(f"[WORKER] >>> Started background ingestion task for document_id: {document_id}")
    logger.info(f"Background worker started for document: {document_id}")
    try:
        await process_document(document_id)
        print(f"[WORKER] >>> Successfully completed background ingestion for document_id: {document_id}")
        logger.info(f"Background worker completed for document: {document_id}")
    except Exception as e:
        print(f"[WORKER] >>> Background worker failed for document_id: {document_id}. Error: {str(e)}")
        logger.error(f"Background worker failed for document {document_id}: {str(e)}")
