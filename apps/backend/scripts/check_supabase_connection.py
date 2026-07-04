import sys
import os
import time

# Add the apps/backend directory to python paths to locate app module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.supabase_client import get_supabase_client
from app.core.config import settings

def check_table(supabase, table_name: str) -> None:
    """
    Checks if a table exists by selecting 1 row with a retry on connection terminations.
    """
    for attempt in range(3):
        try:
            supabase.table(table_name).select("id").limit(1).execute()
            print(f" -> SUCCESS: '{table_name}' table is reachable in the database.")
            return
        except Exception as e:
            err_msg = str(e) or repr(e)
            if ("ConnectionTerminated" in err_msg or "ConnectionTerminated" in repr(e)) and attempt < 2:
                print(f"    (Connection dropped; retrying query for '{table_name}' table in 1s...)")
                time.sleep(1)
                # Re-fetch supabase client to establish fresh connection pool
                supabase = get_supabase_client()
                continue
            else:
                print(f" -> FAILURE: Could not query '{table_name}' table. Check if migrations were run.")
                print(f"    Technical logs: {err_msg}")
                sys.exit(1)

def main():
    print("=" * 60)
    print("          SUPABASE LIVE CONNECTION & SCHEMA CHECKER")
    print("=" * 60)
    
    # 1. Print active configurations safely
    print(f"SUPABASE_URL: {settings.SUPABASE_URL}")
    print(f"SUPABASE_STORAGE_BUCKET: {settings.SUPABASE_STORAGE_BUCKET}")
    print(f"EMBEDDING_MODEL_NAME: {settings.EMBEDDING_MODEL_NAME}")
    
    srv_role = settings.SUPABASE_SERVICE_ROLE_KEY
    anon_key = settings.SUPABASE_KEY
    
    if srv_role:
        print(f"SUPABASE_SERVICE_ROLE_KEY: [Configured] (Starts with: {srv_role[:5]}... Length: {len(srv_role)})")
    else:
        print("SUPABASE_SERVICE_ROLE_KEY: [Not Configured]")
        
    if anon_key:
        print(f"SUPABASE_KEY: [Configured] (Starts with: {anon_key[:5]}... Length: {len(anon_key)})")
    else:
        print("SUPABASE_KEY: [Not Configured]")
        
    if not srv_role and not anon_key:
        print("\nERROR: No Supabase API keys configured! Check your .env configuration.")
        sys.exit(1)
        
    # 2. Connect to Supabase client
    print("\n[1/4] Connecting to Supabase...")
    try:
        supabase = get_supabase_client()
        print(" -> SUCCESS: Supabase client successfully initialized.")
    except Exception as e:
        print(f" -> FAILURE: Failed to initialize Supabase client: {str(e)}")
        sys.exit(1)
        
    # 3. Check documents table
    print("\n[2/4] Checking 'documents' table exists...")
    check_table(supabase, "documents")
        
    # 4. Check document_chunks table
    print("\n[3/4] Checking 'document_chunks' table exists...")
    check_table(supabase, "document_chunks")
        
    # 5. Check study-documents Storage bucket
    print(f"\n[4/4] Checking storage bucket '{settings.SUPABASE_STORAGE_BUCKET}' exists...")
    try:
        supabase.storage.get_bucket(settings.SUPABASE_STORAGE_BUCKET)
        print(f" -> SUCCESS: Storage bucket '{settings.SUPABASE_STORAGE_BUCKET}' exists and is accessible.")
    except Exception as e:
        print(f" -> FAILURE: Storage bucket '{settings.SUPABASE_STORAGE_BUCKET}' not found or permission denied.")
        print("    Ensure you created a private bucket with that exact name in your Storage settings.")
        print(f"    Technical logs: {str(e)}")
        sys.exit(1)
        
    print("\n" + "=" * 60)
    print("CONGRATULATIONS: Backend is successfully connected to Supabase!")
    print("=" * 60)

if __name__ == "__main__":
    main()
