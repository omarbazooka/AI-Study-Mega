import re
from typing import List, Any, Optional
from pydantic import BaseModel

STOPWORDS = {"a", "an", "the", "about", "on", "in", "of", "to", "for", "and", "or", "is", "are"}

class Citation(BaseModel):
    chunk_id: str
    page_number: int
    section_title: Optional[str] = None

class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    score: float = 0.9

def build_citations(retrieved_chunks: List[Any], llm_output: str, source_chunk_ids: Optional[List[str]] = None) -> List[Citation]:
    citations = []
    import re
    
    if not retrieved_chunks or not llm_output:
        print("Empty chunks or output")
        return []
        
    output_lower = llm_output.lower()
    
    for c in retrieved_chunks:
        c_id = c.chunk_id if hasattr(c, "chunk_id") else c.get("id") or c.get("chunk_id")
        text = c.text if hasattr(c, "text") else c.get("content", "")
        page = c.page_number if hasattr(c, "page_number") else c.get("page_start", 1)
        section = c.section_title if hasattr(c, "section_title") else c.get("section_title")
        score = c.score if hasattr(c, "score") else c.get("score", 0.90)

        chunk_cited = False
        if source_chunk_ids and str(c_id) in source_chunk_ids:
            chunk_cited = True
        elif str(c_id).lower() in output_lower:
            chunk_cited = True
        else:
            words = [w for w in re.findall(r"\w{5,}", text.lower()) if w not in STOPWORDS]
            print(f"words: {words}")
            matches = sum(1 for w in words if w in output_lower)
            print(f"matches: {matches}")
            if matches >= 2:
                chunk_cited = True

        if chunk_cited:
            citations.append(Citation(
                chunk_id=str(c_id),
                page_number=page or 1,
                section_title=section or "RAG Pipeline"
            ))
            
    return citations

chunks = [
    RetrievedChunk(chunk_id="chunk-photo-1", text="chloroplast converts sunlight")
]
res = build_citations(chunks, "Sunlight is converted inside the chloroplast.", None)
print(f"Result: {res}")
