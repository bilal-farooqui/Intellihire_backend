from fastapi import APIRouter, Depends
from app.database import (
    employee_collection,
    job_collection,
    application_collection,
    leave_collection,
    settings_collection
)
from app.auth import require_admin

router = APIRouter()

@router.get("/admin-dashboard")
async def get_admin_dashboard_stats(current_user=Depends(require_admin)):
    """
    Get consolidated statistics for the Admin Dashboard.
    Fetches counts for employees, jobs, applications, and leaves in one call.
    """
    # 1. Get counts
    employee_count = await employee_collection.count_documents({})
    job_count = await job_collection.count_documents({"is_active": True})
    application_count = await application_collection.count_documents({})
    
    # 2. Leaves stats
    all_leaves = await leave_collection.count_documents({})
    pending_leaves = await leave_collection.count_documents({"status": {"$regex": "^pending$", "$options": "i"}})
    
    # 3. Settings (Allowed IPs)
    settings = await settings_collection.find_one({})
    allowed_ips = settings.get("allowed_ips", []) if settings else ["127.0.0.1", "::1"]
    
    return {
        "employees": employee_count,
        "jobs": job_count,
        "applications": application_count,
        "leaves": all_leaves,
        "pendingLeaves": pending_leaves,
        "allowed_ips": allowed_ips
    }
