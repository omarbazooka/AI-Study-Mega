import logging
from app.db.supabase_client import get_supabase_client
from app.core.config import settings
from app.db.repositories import document_repository, chunk_repository
from app.ai_system.ingestion.pdf_parser import parse_pdf
from app.ai_system.ingestion.cleaner import clean_text
from app.ai_system.ingestion.chunker import chunk_document
from app.ai_system.ingestion.metadata_generator import generate_chunk_metadata
from app.ai_system.providers.embedding_client import embed_texts

logger = logging.getLogger(__name__)

async def process_document(document_id: str) -> None:
    """
    Coordinates the entire document ingestion workflow in a readable, linear sequence:
    1. Set status to 'parsing'
    2. Download raw PDF file from Supabase Storage
    3. Extract text page-by-page (pypdf)
    4. Set status to 'chunking'
    5. Clean extracted text (cleaner)
    6. Chunk text paragraph-aware (chunker)
    7. Generate metadata for chunks
    8. Set status to 'embedding'
    9. Calculate chunk vectors (sentence-transformers)
    10. Insert chunks + vectors into pgvector
    11. Mark document status to 'ready'
    
    If any error occurs, catches the exception and marks the document as 'failed' with a readable error message.
    """
    supabase = get_supabase_client()
    
    try:
        print(f"[PIPELINE] Starting linear ingestion pipeline for document_id: {document_id}")
        logger.info(f"Starting ingestion pipeline for document {document_id}")
        
        # Step 1: Update status to parsing
        await document_repository.update_status(document_id, "parsing")
        
        # Step 2: Load document metadata from db
        doc = await document_repository.get_by_id(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found in database.")
            
        storage_path = doc.get("storage_path")
        if not storage_path:
            raise ValueError(f"Document {document_id} has no storage path.")
            
        # Step 3: Download file bytes from Supabase Storage
        print(f"[PIPELINE] [1/5] Downloading PDF from bucket '{settings.SUPABASE_STORAGE_BUCKET}' at '{storage_path}'...")
        try:
            file_bytes = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(storage_path)
            print(f"[PIPELINE] Downloaded raw PDF file. Size: {len(file_bytes)} bytes.")
        except Exception as e:
            raise RuntimeError(f"Supabase Storage download failed: {str(e)}")
            
        # Step 4: Parse PDF page-by-page
        print(f"[PIPELINE] [2/5] Parsing PDF pages...")
        pages = parse_pdf(file_bytes)
        page_count = len(pages)
        print(f"[PIPELINE] Extracted {page_count} pages successfully.")
        
        # Step 5: Update status to chunking, clean and chunk
        await document_repository.update_status(document_id, "chunking")
        
        print(f"[PIPELINE] [3/5] Cleaning and chunking text...")
        cleaned_pages = []
        for page in pages:
            cleaned_pages.append({
                "page_number": page["page_number"],
                "text": clean_text(page["text"])
            })
            
        chunks = chunk_document(cleaned_pages)
        if not chunks:
            raise ValueError("Could not generate any chunks from the document text.")
        print(f"[PIPELINE] Generated {len(chunks)} paragraph-aware chunks.")
            
        # Step 6: Generate metadata per chunk
        for chunk in chunks:
            chunk["metadata"] = generate_chunk_metadata(
                document_id=document_id,
                filename=doc["original_filename"],
                chunk_index=chunk["chunk_index"],
                page_start=chunk["page_start"],
                page_end=chunk["page_end"]
            )
            
        # Step 7: Update status to embedding, generate vectors
        await document_repository.update_status(document_id, "embedding")
        
        print(f"[PIPELINE] [4/5] Computing embeddings using model '{settings.EMBEDDING_MODEL_NAME}' (384 dimensions)...")
        chunk_contents = [c["content"] for c in chunks]
        embeddings = embed_texts(chunk_contents)
        print(f"[PIPELINE] Generated {len(embeddings)} embedding vectors.")
        
        # Step 8: Insert chunks into document_chunks
        print(f"[PIPELINE] [5/5] Inserting chunks into PostgreSQL Vector Database...")
        # Ensure we delete any existing chunks first to avoid duplicates on reprocessing
        await chunk_repository.delete_chunks_by_document(document_id)
        inserted_rows = await chunk_repository.insert_chunks(
            document_id=document_id,
            user_id=doc["user_id"],
            chunks=chunks,
            embeddings=embeddings
        )
        print(f"[PIPELINE] Saved {len(inserted_rows)} chunks and vectors to database successfully.")
        
        # Step 9: Mark document as ready
        await document_repository.mark_ready(
            document_id=document_id,
            page_count=page_count,
            chunk_count=len(chunks)
        )
        print(f"[PIPELINE] Ingestion pipeline completed successfully. Document {document_id} is now READY.")
        logger.info(f"Ingestion pipeline completed successfully for document {document_id}")
        
    except Exception as e:
        err_msg = str(e)
        print(f"[PIPELINE] ERROR occurred: {err_msg}")
        logger.exception(f"Ingestion pipeline failed for document {document_id}")
        # Mark document as failed and record readable error message in DB
        await document_repository.mark_failed(document_id, err_msg)
        raise e
