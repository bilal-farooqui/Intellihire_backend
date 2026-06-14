import asyncio
import os
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

async def seed_database():
    print(f"Connecting to: {MONGO_URI}")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_database("HR_System")
    collection = db.get_collection("employees")

    # Hash passwords helper
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    # 1. Admin account details
    admin_email = "crscommunity123@gmail.com"
    admin_password = "ceremidianCS-42"
    
    # Check/Create Admin
    existing_admin = await collection.find_one({"email": admin_email})
    if existing_admin:
        print(f"Admin with email {admin_email} already exists. Updating password...")
        await collection.update_one(
            {"_id": existing_admin["_id"]},
            {"$set": {"password": hash_password(admin_password), "role": "Admin"}}
        )
    else:
        admin_data = {
            "full_name": "System Admin",
            "email": admin_email,
            "password": hash_password(admin_password),
            "employee_code": "ADMIN001",
            "cnic": "0000000000001",
            "role": "Admin",
            "salary": 0.0,
            "mobile": "0000000000",
            "joined_at": datetime.utcnow(),
            "paid_leaves_total": 20,
            "paid_leaves_used": 0
        }
        await collection.insert_one(admin_data)
        print(f"Created Admin: {admin_email} / {admin_password}")

    # 2. Test Employee account details
    emp_email = "employee@example.com"
    emp_password = "password123"
    
    # Check/Create Employee
    existing_emp = await collection.find_one({"email": emp_email})
    if existing_emp:
        print(f"Employee with email {emp_email} already exists. Updating password...")
        await collection.update_one(
            {"_id": existing_emp["_id"]},
            {"$set": {"password": hash_password(emp_password), "role": "Employee"}}
        )
    else:
        emp_data = {
            "full_name": "John Employee",
            "email": emp_email,
            "password": hash_password(emp_password),
            "employee_code": "EMP001",
            "cnic": "1234567890123",
            "role": "Employee",
            "salary": 50000.0,
            "mobile": "03001234567",
            "joined_at": datetime.utcnow(),
            "paid_leaves_total": 20,
            "paid_leaves_used": 0
        }
        await collection.insert_one(emp_data)
        print(f"Created Employee: {emp_email} / {emp_password}")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed_database())
