import motor.motor_asyncio
import os
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URI")

# 0.5. MongoDB connection with timeout
client_kwargs = {
    "serverSelectionTimeoutMS": 5000,
    "maxPoolSize": 50,
    "minPoolSize": 1,
    "connectTimeoutMS": 10000
}

# Only use tlsCAFile if we are not connecting to a local MongoDB instance
if MONGO_URL and "localhost" not in MONGO_URL and "127.0.0.1" not in MONGO_URL:
    client_kwargs["tlsCAFile"] = certifi.where()

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL, **client_kwargs)

# 1. Yeh hai tumhara MAIN DATABASE (Ghar)
database = client.HR_System 

# 2. Yeh hain tumhare COLLECTIONS (Kamray)
# Hum in variables ko pure project mein use karenge data save/get karne ke liye
employee_collection = database.get_collection("employees")
job_collection = database.get_collection("jobs")
application_collection = database.get_collection("applications")
leave_collection = database.get_collection("leaves")
attendance_collection = database.get_collection("attendance")
daily_attendance_collection = database.get_collection("daily_attendance")
settings_collection = database.get_collection("settings")
wfh_collection = database.get_collection("wfh_requests")
payroll_collection = database.get_collection("payroll")
projects_collection = database.get_collection("projects")
timesheets_collection = database.get_collection("timesheets")
messages_collection = database.get_collection("messages")
interviews_collection = database.get_collection("interviews")