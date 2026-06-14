import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

async def check_db():
    client = AsyncIOMotorClient(MONGO_URI)
    dbs = await client.list_database_names()
    print(f"Databases: {dbs}")
    
    db = client.get_database("HR_System")
    collections = await db.list_collection_names()
    print(f"Collections in HR_System: {collections}")
    
    count = await db.get_collection("employees").count_documents({})
    print(f"Employee count: {count}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_db())
