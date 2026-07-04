from pydantic import BaseModel
from typing import Optional

class UploadResponse(BaseModel):
    """
    Response schema returned immediately after document upload.
    """
    document_id: str
    status: str
    message: str

class StatusResponse(BaseModel):
    """
    Response schema returning the current ingestion pipeline status of a document.
    """
    document_id: str
    status: str
    page_count: Optional[int] = None
    chunk_count: Optional[int] = 0
    error_message: Optional[str] = None
