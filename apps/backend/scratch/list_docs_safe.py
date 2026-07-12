import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv("../.env")

import asyncio
from app.db.repositories import document_repository

async def main():
    docs = await document_repository.get_all_by_user_id("c9d079ce-1858-437f-a168-99a85d28218b")
    print("Documents count:", len(docs))
    for doc in docs:
        # Use ascii-safe printing
        print(f"ID: {doc.get('id')}, status: {doc.get('upload_status')}")

asyncio.run(main())
