import os
from dotenv import load_dotenv
load_dotenv(".env")
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing in env.")
    exit(1)

client = create_client(url, key)

print("Listing auth users...")
try:
    users = client.auth.admin.list_users()
    print("Successfully retrieved users via auth.admin.list_users():")
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}")
except Exception as e:
    print(f"Error querying auth.admin.list_users(): {e}")

print("\nTrying to query from documents table to see if any user_id is already used...")
try:
    resp = client.table("documents").select("user_id").limit(10).execute()
    print("Successfully queried documents:")
    user_ids = set(doc["user_id"] for doc in resp.data)
    for uid in user_ids:
        print(f"User ID from documents: {uid}")
except Exception as e:
    print(f"Error querying documents: {e}")
