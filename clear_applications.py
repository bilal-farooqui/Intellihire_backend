import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def delete_all_applications():
    uri = os.getenv("MONGO_URI")
    client = AsyncIOMotorClient(uri)
    db = client.HR_System
    result = await db.applications.delete_many({})
    print(f"Deleted {result.deleted_count} applications from the database.")

if __name__ == "__main__":
    asyncio.run(delete_all_applications())
