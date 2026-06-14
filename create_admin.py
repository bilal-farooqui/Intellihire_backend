import asyncio
import os
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

async def create_admin():
    print(f"Connecting to: {MONGO_URI}")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_database("HR_System")
    collection = db.get_collection("employees")

    # User details
    email = "crscommunity123@gmail.com"
    password = "ceremidianCS-42"
    
    # Check if user already exists
    existing_user = await collection.find_one({"email": email})
    if existing_user:
        print(f"User with email {email} already exists!")
        return

    # Hash password using bcrypt directly
    # passlib bcrypt uses $2b$ and standard salt
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    # Admin data
    admin_data = {
        "full_name": "System Admin",
        "email": email,
        "password": hashed_password,
        "employee_code": "ADMIN001",
        "cnic": "0000000000001",
        "role": "Admin",
        "salary": 0.0,
        "mobile": "0000000000",
        "joined_at": datetime.utcnow(),
        "paid_leaves_total": 20,
        "paid_leaves_used": 0
    }

    try:
        result = await collection.insert_one(admin_data)
        print(f"Admin account created successfully with ID: {result.inserted_id}")
    except Exception as e:
        print(f"Error creating admin account: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_admin())
