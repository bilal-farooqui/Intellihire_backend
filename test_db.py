import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def test_db():
    load_dotenv()
    mongo_url = os.getenv("MONGO_URI")
    print(f"Connecting to: {mongo_url}")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
    try:
        await client.admin.command('ping')
        print("Ping successful!")
        db = client.HR_System
        count = await db.employees.count_documents({})
        print(f"Employee count: {count}")
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
