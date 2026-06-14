from fastapi import APIRouter, Body, UploadFile, File, Form, HTTPException
from typing import List
from app.ai import ai_engine
from pydantic import EmailStr
from uuid import uuid4
from bson import ObjectId
import os
import re
from app.models import ApplicationModel
from app.database import application_collection
from app.cloudinary_config import store_cv_and_get_url

router = APIRouter()

# 1. APPLY FOR JOB (Candidate CV upload karega)
@router.post("/apply")
async def apply_for_job(app: ApplicationModel = Body(...)):
    # TODO: Yahan baad mein AI ka code ayega jo score calculate karega
    # Abhi hum dummy score save kar rahe hain
    app.ai_score = 85 
    
    new_app = await application_collection.insert_one(app.dict())
    return {"message": "Application Submitted", "id": str(new_app.inserted_id)}


# 1.b APPLY FOR JOB WITH PDF FILE
@router.post("/apply-file")
async def apply_for_job_with_file(
    job_id: str = Form(...),
    candidate_name: str = Form(...),
    candidate_email: EmailStr = Form(...),
    file: UploadFile = File(...),
):
    # Sirf PDF allow karo
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Temp file before move to uploads/cv or upload to Cloudinary (opt-in)
    upload_dir = os.path.join("uploads", "temp")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid4().hex}.pdf"
    temp_path = os.path.join(upload_dir, filename)

    try:
        file_bytes = await file.read()
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        cv_url = store_cv_and_get_url(temp_path)

        if not cv_url:
            raise HTTPException(status_code=500, detail="Failed to save CV file")

        app_obj = ApplicationModel(
            job_id=job_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            cv_url=cv_url,
        )

        new_app = await application_collection.insert_one(app_obj.dict())

        return {
            "message": "Application submitted successfully",
            "id": str(new_app.inserted_id),
            "cv_url": cv_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# 2. GET ALL APPLICATIONS (Admin dekhega - for counting unviewed)
# This must come before /{job_id} to avoid route conflicts
@router.get("/all")
async def get_all_applications():
    apps = []
    async for app in application_collection.find():
        app["_id"] = str(app["_id"])
        apps.append(app)
    return apps

# 2.b GET APPLICATIONS BY CANDIDATE EMAIL (Applicant dekhega)
@router.get("/candidate/{candidate_email}")
async def get_applications_by_candidate(candidate_email: str):
    normalized = (candidate_email or "").strip().lower()
    if not normalized:
        return []

    # Case-insensitive exact email match to avoid missing records from casing differences.
    safe_email_regex = {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}
    apps = []
    async for app in application_collection.find({"candidate_email": safe_email_regex}):
        app["_id"] = str(app["_id"])
        apps.append(app)
    return apps

# 2.c GET APPLICATIONS FOR A JOB (HR dekhega)
@router.get("/{job_id}")
async def get_applications_by_job(job_id: str):
    apps = []
    async for app in application_collection.find({"job_id": job_id}):
        app["_id"] = str(app["_id"])
        apps.append(app)
    return apps


# 3. UPDATE APPLICATION STATUS (Shortlist / Reject)
@router.patch("/{application_id}/status")
async def update_application_status(application_id: str, payload: dict = Body(...)):
    status = payload.get("status")
    if status not in {"Pending", "Unviewed", "Viewed", "Shortlisted", "Rejected"}:
        raise HTTPException(status_code=400, detail="Invalid status value")

    try:
        obj_id = ObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid application id")

    result = await application_collection.update_one(
        {"_id": obj_id},
        {"$set": {"status": status}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")

    return {"message": "Status updated", "status": status}


# 4. DELETE APPLICATION
@router.delete("/{application_id}")
async def delete_application(application_id: str):
    try:
        obj_id = ObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid application id")

    result = await application_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")

    return {"message": "Application deleted successfully"}
