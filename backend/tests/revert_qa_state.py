"""QA helper: inspect / revert the payment state touched during UI testing."""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    doc = await db.clients.find_one({"cognome": {"$regex": "giuditta", "$options": "i"}}, {"_id": 0})
    if not doc:
        doc = await db.clients.find_one({"nome": {"$regex": "trio", "$options": "i"}}, {"_id": 0})
    if not doc:
        print("client not found")
    else:
        print({k: v for k, v in doc.items() if "pag" in k or k in ("id", "nome", "cognome")})
        if "--revert" in sys.argv:
            res = await db.clients.update_one(
                {"id": doc["id"]},
                {"$set": {"pagato": False, "data_pagamento": None}},
            )
            print("reverted:", res.modified_count)
    print("TEST_QA leftovers:", await db.clients.count_documents({"nome": "TEST_QA"}))
    print("total clients:", await db.clients.count_documents({}))
    print("test users:", await db.users.count_documents({"email": {"$regex": "^test_qa_"}}))
    if "--revert" in sys.argv:
        r = await db.users.delete_many({"email": {"$regex": "^test_qa_"}})
        print("test users deleted:", r.deleted_count)


asyncio.run(main())
