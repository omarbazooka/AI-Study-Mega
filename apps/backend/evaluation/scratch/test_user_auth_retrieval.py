import os
import sys
from dotenv import load_dotenv

BACKEND = r"c:\Users\omara\OneDrive\Desktop\Machine Leraning DEPI\Mega Project\NHA-4-094\apps\backend"
sys.path.insert(0, BACKEND)
load_dotenv(os.path.join(BACKEND, ".env"))

from evaluation.runners.auth_helper import authenticate_evaluation_user
from app.db.supabase_client import get_supabase_client

async def main():
    user_id, access_token = authenticate_evaluation_user()
    print("User ID:", user_id)
    
    # Get the standard global client
    supabase = get_supabase_client()
    
    # Set the auth JWT token
    supabase.postgrest.auth(access_token)
    
    # 1. Test document visibility
    doc_id = "1ef24635-4f7f-4849-93a7-3a4fc6bf1560" # Arabic Document 2
    try:
        resp = supabase.table("documents").select("id, original_filename, user_id").eq("id", doc_id).execute()
        print("Document visibility response:", resp.data)
    except Exception as e:
        print("Error checking document visibility:", e)
        
    # 2. Test match_document_chunks RPC call
    dummy_vec = [0.0] * 1024
    try:
        rpc_resp = supabase.rpc("match_document_chunks", {
            "query_embedding": dummy_vec,
            "match_threshold": 0.0,
            "match_count": 5,
            "p_user_id": user_id,
            "p_document_id": doc_id
        }).execute()
        print("RPC count retrieved:", len(rpc_resp.data or []))
        if rpc_resp.data:
            print("First chunk sample:", rpc_resp.data[0]["content"][:60])
    except Exception as e:
        print("Error checking RPC:", e)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
