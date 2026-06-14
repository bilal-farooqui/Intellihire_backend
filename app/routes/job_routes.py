from fastapi import APIRouter, HTTPException, Body
from app.models import JobModel
from app.database import job_collection
from typing import List
from fastapi import Depends
from app.auth import require_admin
from app.utils.auth import get_current_user

router = APIRouter()

# 1. CREATE JOB (HR Post karega)
@router.post("/create")
async def create_job(job: JobModel = Body(...), current_user=Depends(require_admin)):
    new_job = await job_collection.insert_one(job.dict())
    return {"message": "Job Posted", "id": str(new_job.inserted_id)}

# 2. GET ALL JOBS (Frontend par dikhane ke liye)
@router.get("/all")
async def get_all_jobs():
    jobs = []
    # Sirf active jobs dikhao
    async for job in job_collection.find({"is_active": True}):
        job["_id"] = str(job["_id"])
        jobs.append(job)
    return jobs

# 3. GET JOB RECOMMENDATIONS (AI Powered)
@router.get("/recommendations")
async def get_recommendations(current_user=Depends(get_current_user)):
    from app.database import employee_collection
    from app.ai.engine import ai_engine
    
    email = current_user.get("sub")
    
    # 1. Get Applicant Profile
    applicant = await employee_collection.find_one({"email": email})
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
        
    # Get supplies from distilled profile
    distilled = applicant.get("distilled_profile", {})
    if not distilled:
        # If profile not distilled yet, return jobs with 0 score
        jobs = []
        async for job in job_collection.find({"is_active": True}):
            job["_id"] = str(job["_id"])
            job["match_score"] = 0
            job["match_reasoning"] = "Complete your AI profile setup to see match scores."
            jobs.append(job)
        return jobs

    supplies = distilled.get("supplies", [])
    
    # 2. Get All Active Jobs
    jobs = []
    async for job in job_collection.find({"is_active": True}):
        job["_id"] = str(job["_id"])
        jobs.append(job)
        
    if not jobs:
        return []
        
    # 3. AI Match
    recommendations = await ai_engine.match_applicant_to_jobs(supplies, jobs)
    
    # 4. Merge results
    final_jobs = []
    rec_map = {r["job_id"]: r for r in recommendations}
    
    for j in jobs:
        match_info = rec_map.get(j["_id"], {"match_score": 0, "reasoning": "Matching analysis pending."})
        j["match_score"] = match_info.get("match_score", 0)
        j["match_reasoning"] = match_info.get("reasoning", "")
        final_jobs.append(j)
        
    # Sort by score
    final_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    return final_jobs

# 4. DELETE JOB (ADMIN ONLY)
@router.delete("/delete/{job_id}")
async def delete_job(job_id: str, current_user=Depends(require_admin)):
    from bson import ObjectId
    from app.database import application_collection, interviews_collection
    
    try:
        obj_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Job ID format")
        
    res = await job_collection.delete_one({"_id": obj_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job opening not found")
        
    # Cascade delete associated records
    await application_collection.delete_many({"job_id": job_id})
    await interviews_collection.delete_many({"job_id": job_id})
    
    return {"message": "Job opening and associated applications/interviews deleted successfully"}
