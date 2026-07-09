"""
Check documents in Supabase DB + storage bucket status.
Run: python check_doc_status.py
"""
import os
from dotenv import load_dotenv
load_dotenv(".env")

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "study-documents")

client = create_client(url, key)

print("=" * 55)
print("  DOCUMENT STATUS IN SUPABASE")
print("=" * 55)

try:
    resp = client.table("documents").select("*").order("created_at", desc=True).limit(10).execute()
    docs = resp.data
    if not docs:
        print("No documents found in the database.")
    else:
        for doc in docs:
            print(f"\n  ID     : {doc.get('id')}")
            print(f"  File   : {doc.get('original_filename')}")
            print(f"  Status : {doc.get('upload_status')}")
            print(f"  Chunks : {doc.get('chunk_count')}")
            print(f"  Path   : {doc.get('storage_path')}")
except Exception as e:
    print(f"  DB Error: {e}")

print("\n" + "=" * 55)
print("  STORAGE BUCKET STATUS")
print("=" * 55)

try:
    buckets = client.storage.list_buckets()
    names = [b.name for b in buckets]
    if bucket in names:
        print(f"  Bucket '{bucket}': EXISTS")
        # List files
        files = client.storage.from_(bucket).list()
        if files:
            print(f"  Files in bucket ({len(files)}):")
            for f in files[:5]:
                print(f"    - {f.get('name')}")
        else:
            print("  Bucket is empty (no files uploaded yet)")
    else:
        print(f"  Bucket '{bucket}': MISSING!")
        print(f"  Available buckets: {names}")
        print()
        print("  FIX: Go to Supabase Dashboard -> Storage -> New bucket")
        print(f"       Name: {bucket}, Type: Private")
except Exception as e:
    print(f"  Storage Error: {e}")
