import os
from app.core.config import settings

def validate_pdf(
    file_bytes: bytes,
    filename: str,
    content_type: str = None
) -> None:
    """
    Validates that the uploaded file is a valid PDF and does not violate size constraints.
    Raises ValueError if validation fails.
    """
    # 1. Check for empty files
    if not file_bytes or len(file_bytes) == 0:
        raise ValueError("File is empty.")

    # 2. Check for file size limits
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValueError(f"File size exceeds the limit of {settings.MAX_UPLOAD_SIZE_MB} MB.")

    # 3. Check the file extension
    _, ext = os.path.splitext(filename)
    if ext.lower() != ".pdf":
        raise ValueError("Unsupported file type. Only .pdf files are accepted.")

    # 4. Validate MIME/content-type if provided by request
    if content_type and content_type.lower() != "application/pdf":
        raise ValueError("Invalid content type. Expected application/pdf.")

    # 5. Validate PDF header magic bytes (%PDF)
    # The header of a valid PDF starts with %PDF (hex: 25 50 44 46)
    if len(file_bytes) >= 4 and file_bytes[:4] != b"%PDF":
        raise ValueError("Invalid file structure. The file is not a valid PDF document.")
