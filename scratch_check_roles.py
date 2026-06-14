import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def check_roles():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.HR_System
    async for e in db.employees.find():
        print(f"Name: {e.get('full_name')}, Role: {e.get('role')}")

if __name__ == "__main__":
    asyncio.run(check_roles())
