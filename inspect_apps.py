import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

async def inspect_applications():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.HR_System
    apps = await db.applications.find().to_list(100)
    for app in apps:
        print(f"Name: {app.get('candidate_name')}, Email: {app.get('candidate_email')}, CV URL: {app.get('cv_url')}")
    client.close()

if __name__ == "__main__":
    asyncio.run(inspect_applications())
