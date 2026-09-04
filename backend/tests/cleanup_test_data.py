"""Cleanup script: removes QA test artifacts created during E2E testing."""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    ids = [c["id"] async for c in db.clients.find(
        {"$or": [{"nome": {"$regex": "^(TEST_|Test$)"}}, {"cognome": {"$regex": "^(TEST_|Verifica$)"}}]}, {"id": 1})]
    print("clients removed:", (await db.clients.delete_many({"id": {"$in": ids}})).deleted_count)
    if ids:
        await db.lavorazioni_log.delete_many({"client_id": {"$in": ids}})
    print("stores removed:", (await db.stores.delete_many({"nome": {"$regex": "^TEST_"}})).deleted_count)
    print("users removed:", (await db.users.delete_many({"email": {"$regex": "^test_"}})).deleted_count)
    # revert store payments toggled by tests
    print("stores payment reverted:", (await db.stores.update_many(
        {"nome": {"$in": ["Tirano", "Sondalo"]}},
        {"$set": {"pagato": False, "last_payment_date": None}})).modified_count)
    print("clients:", await db.clients.count_documents({}), "stores:", await db.stores.count_documents({}),
          "users:", await db.users.count_documents({}))


asyncio.run(main())
