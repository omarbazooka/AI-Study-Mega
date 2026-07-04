from app.ai_system.ingestion.chunker import chunk_document

def test_chunk_document_fields():
    """
    Ensures that every chunk returned has the correct fields and types.
    """
    pages = [
        {"page_number": 1, "text": "This is paragraph one.\n\nThis is paragraph two."},
        {"page_number": 2, "text": "This is paragraph three on page two."}
    ]
    
    chunks = chunk_document(pages, chunk_size=100, chunk_overlap=10)
    
    assert len(chunks) > 0
    for chunk in chunks:
        assert "chunk_index" in chunk
        assert "content" in chunk
        assert "page_start" in chunk
        assert "page_end" in chunk
        assert isinstance(chunk["chunk_index"], int)
        assert isinstance(chunk["content"], str)
        assert isinstance(chunk["page_start"], int)
        assert isinstance(chunk["page_end"], int)

def test_chunk_document_paragraph_respect():
    """
    Ensures paragraphs are kept intact if they fit inside the chunk size.
    """
    pages = [
        {"page_number": 1, "text": "Short. \n\nAnother short paragraph."}
    ]
    # A chunk size of 100 easily fits both short paragraphs
    chunks = chunk_document(pages, chunk_size=100, chunk_overlap=10)
    
    # Because both fit, it should aggregate them into a single chunk
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Short.\n\nAnother short paragraph."
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 1

def test_chunk_document_page_tracking():
    """
    Verifies that the chunker accurately tracks page spans for chunks that consolidate
    content across page boundaries.
    """
    pages = [
        {"page_number": 1, "text": "This is page 1 notes."},
        {"page_number": 2, "text": "This is page 2 notes."}
    ]
    
    # Set chunk size large enough to aggregate both pages
    chunks = chunk_document(pages, chunk_size=100, chunk_overlap=10)
    
    assert len(chunks) == 1
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 2
