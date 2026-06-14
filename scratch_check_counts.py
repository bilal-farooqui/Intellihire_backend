import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def check_counts():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.HR_System
    collections = ['employees', 'jobs', 'applications', 'leaves', 'settings']
    for col_name in collections:
        count = await db[col_name].count_documents({})
        print(f"{col_name}: {count}")

if __name__ == "__main__":
    asyncio.run(check_counts())
