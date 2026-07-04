from typing import List, Dict, Any

def chunk_document(
    pages: List[Dict[str, Any]],
    chunk_size: int = 800,
    chunk_overlap: int = 150
) -> List[Dict[str, Any]]:
    """
    Splits document pages into paragraph-aware text chunks.
    Tracks starting and ending pages for each chunk.
    
    Args:
        pages: List of dictionaries containing page_number and cleaned text.
        chunk_size: Target maximum size of each chunk in characters.
        chunk_overlap: The character-based overlap between consecutive chunks.
        
    Returns:
        A list of dictionaries representing chunks. Each chunk contains:
        - chunk_index (int)
        - content (str)
        - page_start (int)
        - page_end (int)
    """
    # 1. Flatten all pages into paragraphs with their respective page numbers
    paragraphs = []
    for page in pages:
        page_num = page["page_number"]
        page_text = page["text"]
        
        # Split on double newlines to find paragraph boundaries
        raw_paras = page_text.split("\n\n")
        for para in raw_paras:
            cleaned_para = para.strip()
            if cleaned_para:
                paragraphs.append((cleaned_para, page_num))
                
    # Fallback if no paragraphs are found: treat each page text as a paragraph
    if not paragraphs:
        for page in pages:
            text = page["text"].strip()
            if text:
                paragraphs.append((text, page["page_number"]))

    chunks = []
    current_chunk_text = ""
    current_page_start = None
    current_page_end = None
    chunk_index = 0
    
    i = 0
    while i < len(paragraphs):
        para_text, page_num = paragraphs[i]
        
        # Track starting and ending page for the current chunk
        if current_page_start is None:
            current_page_start = page_num
        current_page_end = page_num
        
        if not current_chunk_text:
            current_chunk_text = para_text
            i += 1
        elif len(current_chunk_text) + 2 + len(para_text) <= chunk_size:
            # Paragraph fits in current chunk
            current_chunk_text += "\n\n" + para_text
            i += 1
        else:
            # Current chunk is full, save it
            chunks.append({
                "chunk_index": chunk_index,
                "content": current_chunk_text,
                "page_start": current_page_start,
                "page_end": current_page_end
            })
            chunk_index += 1
            
            # Implement overlap: look back to see if we can reuse previous paragraphs
            overlap_text = ""
            back_step = 0
            while True:
                idx_to_check = i - 1 - back_step
                if idx_to_check < 0:
                    break
                prev_para = paragraphs[idx_to_check][0]
                if len(overlap_text) + len(prev_para) <= chunk_overlap:
                    overlap_text = prev_para + ("\n\n" if overlap_text else "") + overlap_text
                    back_step += 1
                else:
                    break
            
            # Setup next chunk state
            if back_step > 0:
                i = i - back_step
            else:
                # If paragraph itself is larger than chunk_size, split it by character limit to prevent infinite loops
                if len(para_text) > chunk_size:
                    start_char = 0
                    para_len = len(para_text)
                    while start_char < para_len:
                        end_char = min(start_char + chunk_size, para_len)
                        sub_text = para_text[start_char:end_char]
                        chunks.append({
                            "chunk_index": chunk_index,
                            "content": sub_text,
                            "page_start": page_num,
                            "page_end": page_num
                        })
                        chunk_index += 1
                        start_char += (chunk_size - chunk_overlap)
                    i += 1
            
            current_chunk_text = ""
            current_page_start = None
            current_page_end = None
            
    # Finalize any residual chunk text
    if current_chunk_text:
        chunks.append({
            "chunk_index": chunk_index,
            "content": current_chunk_text,
            "page_start": current_page_start,
            "page_end": current_page_end
        })
        
    return chunks
