import asyncio
import os
from dotenv import load_dotenv
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from jose import jwt

async def test_login():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    print(f"Connecting to: {mongo_uri}")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.HR_System
    user = await db.employees.find_one({"email": "crscommunity123@gmail.com"})
    if not user:
        print("User not found in DB!")
        return
    
    print("User found:", user["email"])
    
    # Test bcrypt
    password = "ceremidianCS-42"
    matched = bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8'))
    print("Bcrypt password match:", matched)
    
    # Test jwt
    SECRET_KEY = os.getenv("SECRET_KEY", "intellihire_secret_key_2025_fyp_deepanalysis")
    ALGORITHM = "HS256"
    to_encode = {"sub": user["email"], "role": user["role"], "id": str(user["_id"])}
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    print("JWT generated successfully:", encoded_jwt)

if __name__ == "__main__":
    asyncio.run(test_login())
