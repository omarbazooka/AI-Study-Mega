"""Check all chunks for the CV document."""
from dotenv import load_dotenv
load_dotenv(".env")
import os
from supabase import create_client

client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
DOCUMENT_ID = "12d9c374-70fb-472f-a5b0-640c1da59b66"

resp = client.table("document_chunks").select("chunk_index, content, page_start").eq(
    "document_id", DOCUMENT_ID
).order("chunk_index").execute()

print(f"Total chunks in CV: {len(resp.data)}")
print()
for c in resp.data:
    idx = c["chunk_index"]
    page = c["page_start"]
    text = c["content"][:250].replace("\n", " ")
    print(f"[{idx}] page={page}: {text}")
    print()
