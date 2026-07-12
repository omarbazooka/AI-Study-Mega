import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv("../.env")

import asyncio
from app.db.repositories import document_repository

async def main():
    doc_id = "f872eeee-cd0e-48ae-96d3-b5f182be7688"
    doc = await document_repository.get_by_id(doc_id)
    if doc:
        print("Document ID:", doc.get("id"))
        print("User ID:", doc.get("user_id"))
        print("Upload Status:", doc.get("upload_status"))
    else:
        print("Document not found")

asyncio.run(main())
