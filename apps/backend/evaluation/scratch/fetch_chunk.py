import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db.supabase_client import get_supabase_client
import asyncio

async def main():
    supabase = get_supabase_client()
    res = supabase.table("document_chunks").select("*").eq("id", "89d9a844-6fcd-4442-a950-057e775c1873").execute()
    print("Res count:", len(res.data))
    if res.data:
        print("Content:", res.data[0].get("content") or res.data[0].get("text"))

if __name__ == "__main__":
    asyncio.run(main())
