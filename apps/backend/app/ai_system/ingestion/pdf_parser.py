import io
from typing import List, Dict, Any
from pypdf import PdfReader

def parse_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extracts text page-by-page from raw PDF file bytes.
    
    Returns:
        List of dicts, each with "page_number" (1-indexed) and "text" (extracted string).
        
    Raises:
        ValueError: If PDF is corrupt, has no pages, or contains no extractable text.
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        
        pages_data = []
        total_extracted_chars = 0
        
        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            text = page.extract_text() or ""
            pages_data.append({
                "page_number": page_num,
                "text": text
            })
            total_extracted_chars += len(text.strip())
            
        if not pages_data:
            raise ValueError("The PDF document does not contain any pages.")
            
        if total_extracted_chars == 0:
            raise ValueError("Could not extract readable text from this PDF.")
            
        return pages_data
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Failed to parse PDF document: {str(e)}")
