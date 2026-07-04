import pytest
from app.ai_system.ingestion.document_validator import validate_pdf
from app.core.config import settings

def test_validate_pdf_success():
    """
    Ensures that a valid PDF with correct magic bytes, extension, and size passes validation.
    """
    valid_pdf_bytes = b"%PDF-1.5\n%..."
    # Should not raise any exceptions
    validate_pdf(valid_pdf_bytes, "math_lesson.pdf", "application/pdf")

def test_validate_pdf_empty():
    """
    Ensures empty PDF bytes are rejected.
    """
    with pytest.raises(ValueError, match="File is empty"):
        validate_pdf(b"", "empty.pdf", "application/pdf")

def test_validate_pdf_unsupported_extension():
    """
    Ensures non-pdf files (e.g. .docx, .txt) are rejected.
    """
    with pytest.raises(ValueError, match="Unsupported file type"):
        validate_pdf(b"%PDF-1.5", "notes.txt", "application/pdf")

def test_validate_pdf_invalid_content_type():
    """
    Ensures that mismatched MIME content types are rejected.
    """
    with pytest.raises(ValueError, match="Invalid content type"):
        validate_pdf(b"%PDF-1.5", "notes.pdf", "text/plain")

def test_validate_pdf_corrupt_magic_bytes():
    """
    Ensures PDF files that don't start with %PDF magic bytes are rejected.
    """
    with pytest.raises(ValueError, match="Invalid file structure"):
        validate_pdf(b"SPACES_BEFORE_%PDF-1.5", "notes.pdf", "application/pdf")

def test_validate_pdf_oversized():
    """
    Ensures files exceeding MAX_UPLOAD_SIZE_MB are rejected.
    """
    original_limit = settings.MAX_UPLOAD_SIZE_MB
    try:
        # Mock limit to 1MB for the test
        settings.MAX_UPLOAD_SIZE_MB = 1
        # Create a file that is exactly 1.1MB
        oversized_bytes = b"%PDF" + (b"0" * (11 * 100 * 1024))
        with pytest.raises(ValueError, match="exceeds the limit"):
            validate_pdf(oversized_bytes, "huge_book.pdf", "application/pdf")
    finally:
        # Restore the original limit
        settings.MAX_UPLOAD_SIZE_MB = original_limit
