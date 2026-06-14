import asyncio
import os
import time
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def profile_db():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    print(f"Profiling connection to: {mongo_uri[:30]}...")
    
    start_time = time.time()
    client = AsyncIOMotorClient(mongo_uri)
    conn_time = time.time() - start_time
    print(f"Client init time: {conn_time:.4f}s")
    
    db = client.HR_System
    
    for i in range(5):
        start = time.time()
        await db.command("ping")
        latency = time.time() - start
        print(f"Ping {i+1} latency: {latency:.4f}s")
        
    start = time.time()
    count = await db.employees.count_documents({})
    query_latency = time.time() - start
    print(f"Simple query latency: {query_latency:.4f}s")

if __name__ == "__main__":
    asyncio.run(profile_db())
