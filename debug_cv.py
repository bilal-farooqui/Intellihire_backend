import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

async def check_app():
    uri = os.getenv("MONGO_URI")
    client = AsyncIOMotorClient(uri)
    db = client.HR_System
    cursor = db.applications.find({"candidate_name": "bilal farooqui"})
    async for app in cursor:
        print(f"Candidate: {app.get('candidate_name')}, CV URL: {app.get('cv_url')}")
    else:
        print("Application not found in database.")

if __name__ == "__main__":
    asyncio.run(check_app())
