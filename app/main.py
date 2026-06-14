from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import database
import os
print("MONGO_URI:", os.getenv("MONGO_URI"))

# Saare Routes Import karo
from app.routes import (
    employee_routes,
    job_routes,
    application_routes,
    leave_routes,
    attendance_routes,
    settings_routes,
    stats_routes,
    wfh_routes,
    payroll_routes,
    extra_routes,
    interview_routes,
)
from app.ai import router as ai_router
from app.routes import auth_google

app = FastAPI()

# PDF uploads ke liye static folder mount karo (Vercel safe)
if os.environ.get("VERCEL"):
    os.makedirs("/tmp/uploads/cv", exist_ok=True)
else:
    os.makedirs("uploads/cv", exist_ok=True)
    app.mount("/static", StaticFiles(directory="uploads"), name="static")
    app.mount("/api/static", StaticFiles(directory="uploads"), name="api_static")

print("\n" + "="*50)
print("HR System Backend is starting...")
print("URL: http://127.0.0.1:8000")
print("="*50 + "\n")

# --- CORS SETTING (Bohat Zaroori for Frontend Connection) ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://intellihire-frontend.vercel.app",
    "https://intellihire-frontend-git-main-bilal-farooquis-projects.vercel.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    try:
        import time
        start_time = time.time()
        # Check if database is connected
        await database.command("ping")
        latency = (time.time() - start_time) * 1000
        print(f"DATABASE CONNECTED SUCCESSFULLY in {latency:.2f}ms!")
    except Exception as e:
        print(f"DATABASE CONNECTION FAILED: {e}")
        print("Tip: Make sure MongoDB is running on your local machine.")

@app.get("/")
async def read_root():
    return {"message": "HR System Backend is Fully Ready!"}

# --- ROUTERS REGISTER KARO ---
app.include_router(employee_routes.router, prefix="/api/employee", tags=["Employee"])
app.include_router(job_routes.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(application_routes.router, prefix="/api/applications", tags=["Applications"])
app.include_router(leave_routes.router, prefix="/api/leaves", tags=["Leaves"])
app.include_router(attendance_routes.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Settings"])
app.include_router(stats_routes.router, prefix="/api/stats", tags=["Stats"])
app.include_router(wfh_routes.router, prefix="/api/wfh", tags=["WFH"])
app.include_router(payroll_routes.router, prefix="/api/payroll", tags=["Payroll"])
app.include_router(extra_routes.router, prefix="/api/extra", tags=["Extra"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(auth_google.router, prefix="/api/auth", tags=["Google Auth"])
app.include_router(interview_routes.router, prefix="/api/interviews", tags=["Interviews"])
