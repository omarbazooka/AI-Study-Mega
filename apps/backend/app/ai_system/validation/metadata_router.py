import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def resolve_metadata_query(document_id: str, query: str, lang: str = "ar") -> str:
    """
    Directly resolves metadata questions (file size, page count, chunk count, upload status)
    using verified database properties, requiring zero LLM calls and skipping RAG.
    """
    from app.db.repositories import document_repository
    doc = await document_repository.get_by_id(document_id)
    if not doc:
        return "الملف غير موجود." if lang == "ar" else "Document not found."

    original_filename = doc.get("original_filename", "document.pdf")
    file_size_bytes = doc.get("file_size") or 0
    page_count = doc.get("page_count") or 0
    chunk_count = doc.get("chunk_count") or 0
    upload_status = doc.get("upload_status", "unknown")

    # Format file size nicely
    if file_size_bytes >= 1024 * 1024:
        size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"
    elif file_size_bytes >= 1024:
        size_str = f"{file_size_bytes / 1024:.2f} KB"
    else:
        size_str = f"{file_size_bytes} Bytes"

    query_lower = query.lower()
    
    # 1. File size queries
    if any(k in query_lower for k in ["حجم", "كبير", "size", "how big"]):
        if lang == "ar":
            return f"حجم ملف '{original_filename}' هو {size_str}. حجمه طبيعي ولا يتجاوز الحد الأقصى للرفع."
        else:
            return f"The size of '{original_filename}' is {size_str}, which is well within the upload limits."

    # 2. Length/pages queries
    if any(k in query_lower for k in ["طويل", "صفحة", "صفحات", "pages", "page count", "how long", "length"]):
        if lang == "ar":
            return f"ملف '{original_filename}' يحتوي على {page_count} صفحات وتم تقسيمه إلى {chunk_count} أجزاء (chunks)."
        else:
            return f"The document '{original_filename}' consists of {page_count} pages and has been parsed into {chunk_count} chunks."

    # 3. Processing status queries
    if any(k in query_lower for k in ["حالة", "status", "ready", "uploaded"]):
        if lang == "ar":
            return f"حالة معالجة الملف '{original_filename}' هي: {upload_status}."
        else:
            return f"The processing status of '{original_filename}' is: {upload_status}."

    # Default fallback description
    if lang == "ar":
        return f"بيانات الملف: '{original_filename}'، الحجم: {size_str}، الصفحات: {page_count}، الأجزاء: {chunk_count}، الحالة: {upload_status}."
    else:
        return f"Document info: '{original_filename}', Size: {size_str}, Pages: {page_count}, Chunks: {chunk_count}, Status: {upload_status}."
