from fastapi import APIRouter, Body, HTTPException, Depends
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timedelta
from app.models import InterviewModel
from app.database import interviews_collection, employee_collection, job_collection, client, application_collection
from app.auth import require_admin, require_employee
from app.utils.auth import get_current_user
import os

router = APIRouter()

# Helper function to generate next 3 working days options (Legacy)
def generate_standard_slots() -> List[str]:
    slots = []
    current_date = datetime.now()
    working_days_added = 0
    
    # Timeslots configuration
    times = ["11:00 AM", "02:00 PM", "04:00 PM"]
    
    while working_days_added < 3:
        current_date += timedelta(days=1)
        # 0 = Monday, 6 = Sunday. We want Monday (0) to Friday (4)
        if current_date.weekday() < 5:
            # Format: DayOfWeek, Month Day | Time
            day_str = current_date.strftime("%A, %B %d")
            time_str = times[working_days_added]
            slots.append(f"{day_str} | {time_str}")
            working_days_added += 1
            
    return slots

# Helper to parse formatted date and time strings into a datetime object
def parse_date_time_strings(date_str: str, time_str: str) -> Optional[datetime]:
    if not date_str or not time_str:
        return None
    try:
        # Expected format: "Monday, June 15, 2026" + "11:00 AM"
        full_str = f"{date_str.strip()} {time_str.strip()}"
        return datetime.strptime(full_str, "%A, %B %d, %Y %I:%M %p")
    except Exception as e:
        print(f"Error parsing date with year: {e}")
        # Try fallback if year is missing (legacy formatting like "Monday, June 15")
        try:
            full_str_no_year = f"{date_str.strip()} {time_str.strip()}"
            current_year = datetime.now().year
            dt = datetime.strptime(full_str_no_year, "%A, %B %d %I:%M %p")
            return dt.replace(year=current_year)
        except Exception as e2:
            print(f"Fallback parsing failed: {e2}")
            return None

# Helper to find the next working day starting at 09:00 AM
def get_baseline_start_time() -> datetime:
    now = datetime.now()
    current = now + timedelta(days=1)
    while current.weekday() >= 5: # 5 = Saturday, 6 = Sunday
        current += timedelta(days=1)
    return current.replace(hour=9, minute=0, second=0, microsecond=0)

# Helper to get the next valid interview slot bypassing weekends and non-business hours
def get_next_valid_slot(current_slot: datetime) -> datetime:
    current = current_slot
    while True:
        # If weekend, advance to next Monday at 09:00 AM
        if current.weekday() >= 5:
            days_to_add = 7 - current.weekday()
            current = current + timedelta(days=days_to_add)
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
            continue
        
        # If before business hours (09:00 AM), set to 09:00 AM same day
        if current.hour < 9:
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
            continue
            
        # If starts after 04:00 PM, advance to next working day at 09:00 AM
        if current.hour >= 17 or (current.hour == 16 and current.minute > 0):
            current = current + timedelta(days=1)
            current = current.replace(hour=9, minute=0, second=0, microsecond=0)
            continue
            
        # Valid slot found
        break
    return current

# 1. SCHEDULE MANUAL (ADMIN ONLY)
@router.post("/schedule-manual")
async def schedule_manual(payload: dict = Body(...), current_user=Depends(require_admin)):
    applicant_id = payload.get("applicant_id")
    job_id = payload.get("job_id")
    interview_date = payload.get("interview_date")
    time_slot = payload.get("time_slot")
    
    if not applicant_id or not job_id or not interview_date or not time_slot:
        raise HTTPException(status_code=400, detail="Missing required scheduling fields")
        
    # Check if existing interview request exists
    existing = await interviews_collection.find_one({"applicant_id": applicant_id, "job_id": job_id})
    
    interview_timestamp = parse_date_time_strings(interview_date, time_slot)
    
    update_fields = {
        "applicant_id": applicant_id,
        "job_id": job_id,
        "interview_date": interview_date,
        "time_slot": time_slot,
        "interview_timestamp": interview_timestamp,
        "mode": "Manual",
        "suggested_slots": [],
        "status": "Scheduled",
        "meeting_link": "https://meet.google.com/interview-room",
        "created_at": datetime.utcnow()
    }
    
    if existing:
        await interviews_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": update_fields}
        )
        interview_id = str(existing["_id"])
    else:
        new_int = await interviews_collection.insert_one(update_fields)
        interview_id = str(new_int.inserted_id)
        
    return {"message": "Interview manually scheduled successfully", "id": interview_id, "status": "Scheduled"}

# 2. INITIATE AUTOMATION (ADMIN ONLY - Legacy)
@router.post("/initiate-automation")
async def initiate_automation(payload: dict = Body(...), current_user=Depends(require_admin)):
    applicant_id = payload.get("applicant_id")
    job_id = payload.get("job_id")
    
    if not applicant_id or not job_id:
        raise HTTPException(status_code=400, detail="Missing applicant_id or job_id")
        
    suggested_slots = generate_standard_slots()
    
    existing = await interviews_collection.find_one({"applicant_id": applicant_id, "job_id": job_id})
    
    update_fields = {
        "applicant_id": applicant_id,
        "job_id": job_id,
        "interview_date": None,
        "time_slot": None,
        "interview_timestamp": None,
        "mode": "Automated",
        "suggested_slots": suggested_slots,
        "status": "Awaiting_Scheduling",
        "meeting_link": "",
        "created_at": datetime.utcnow()
    }
    
    if existing:
        await interviews_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": update_fields}
        )
        interview_id = str(existing["_id"])
    else:
        new_int = await interviews_collection.insert_one(update_fields)
        interview_id = str(new_int.inserted_id)
        
    return {
        "message": "AI smart-slot automation initiated",
        "id": interview_id,
        "status": "Awaiting_Scheduling",
        "suggested_slots": suggested_slots
    }

# 3. CONFIRM SLOT (APPLICANT OR GENERAL - Legacy Support)
@router.patch("/confirm-slot")
async def confirm_slot(payload: dict = Body(...)):
    interview_id = payload.get("interview_id")
    chosen_slot = payload.get("chosen_slot")
    
    if not interview_id or not chosen_slot:
        raise HTTPException(status_code=400, detail="Missing interview_id or chosen_slot")
        
    try:
        obj_id = ObjectId(interview_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid interview ID")
        
    # Split chosen_slot e.g. "Monday, June 15 | 11:00 AM" into date and time
    parts = chosen_slot.split("|")
    date_part = parts[0].strip()
    time_part = parts[1].strip() if len(parts) > 1 else ""
    
    interview_timestamp = parse_date_time_strings(date_part, time_part)

    transaction_success = False
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                existing = await interviews_collection.find_one({"_id": obj_id}, session=session)
                if not existing:
                    raise HTTPException(status_code=404, detail="Interview request not found")
                
                if existing.get("status") != "Awaiting_Scheduling":
                    raise HTTPException(status_code=400, detail="Interview is already scheduled or completed")

                await interviews_collection.update_one(
                    {"_id": obj_id},
                    {
                        "$set": {
                            "status": "Scheduled",
                            "interview_date": date_part,
                            "time_slot": time_part,
                            "interview_timestamp": interview_timestamp,
                            "suggested_slots": []
                        }
                    },
                    session=session
                )
                transaction_success = True
    except Exception as tx_err:
        if isinstance(tx_err, HTTPException):
            raise tx_err
        print(f"Transaction failed, falling back to atomic update check: {tx_err}")

    if not transaction_success:
        result = await interviews_collection.update_one(
            {
                "_id": obj_id,
                "status": "Awaiting_Scheduling"
            },
            {
                "$set": {
                    "status": "Scheduled",
                    "interview_date": date_part,
                    "time_slot": time_part,
                    "interview_timestamp": interview_timestamp,
                    "suggested_slots": []
                }
            }
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to schedule slot. It may have already been scheduled or cancelled.")
            
    return {"message": "Slot confirmed", "status": "Scheduled", "interview_date": date_part, "time_slot": time_part}

# 4. GET ALL INTERVIEWS (ADMIN ONLY)
@router.get("/all")
async def get_all_interviews(current_user=Depends(require_admin)):
    interviews = []
    async for item in interviews_collection.find():
        item["_id"] = str(item["_id"])
        
        # Format interview_timestamp if it is a datetime object to ISO string
        if item.get("interview_timestamp"):
            item["interview_timestamp"] = item["interview_timestamp"].isoformat()
            
        # Populate Candidate Details
        candidate = await employee_collection.find_one({"email": item["applicant_id"]})
        if not candidate:
            candidate = await employee_collection.find_one({"employee_code": item["applicant_id"]})
            
        if candidate:
            item["candidate_name"] = candidate.get("full_name", "N/A")
            item["candidate_email"] = candidate.get("email", "N/A")
        else:
            item["candidate_name"] = "Unknown Candidate"
            item["candidate_email"] = item["applicant_id"]
            
        # Populate Job Title
        try:
            job = await job_collection.find_one({"_id": ObjectId(item["job_id"])})
            item["job_title"] = job.get("title", "Unknown Position") if job else "Unknown Position"
        except Exception:
            item["job_title"] = "Unknown Position"
            
        interviews.append(item)
        
    return interviews

# 5. GET INTERVIEWS FOR APPLICANT (APPLICANT ONLY)
@router.get("/applicant/{applicant_id}")
async def get_applicant_interview(applicant_id: str):
    interviews = []
    async for item in interviews_collection.find({"applicant_id": applicant_id}):
        item["_id"] = str(item["_id"])
        
        if item.get("interview_timestamp"):
            item["interview_timestamp"] = item["interview_timestamp"].isoformat()
            
        try:
            job = await job_collection.find_one({"_id": ObjectId(item["job_id"])})
            item["job_title"] = job.get("title", "Unknown Position") if job else "Unknown Position"
        except Exception:
            item["job_title"] = "Unknown Position"
            
        interviews.append(item)
        
    return interviews

# 6. SCHEDULE SEQUENTIAL (ADMIN ONLY)
@router.post("/schedule-sequential")
async def schedule_sequential(payload: dict = Body(...), current_user=Depends(require_admin)):
    job_id = payload.get("job_id")
    applicant_ids = payload.get("applicant_ids")
    
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing required job_id field")
        
    # If applicant_ids is not provided, fetch all shortlisted candidates for this job
    if not applicant_ids:
        shortlisted_apps = []
        async for app in application_collection.find({"job_id": job_id, "status": "Shortlisted"}):
            email = app.get("candidate_email")
            if email:
                shortlisted_apps.append(email)
        applicant_ids = shortlisted_apps
        
    if not applicant_ids:
        return {"message": "No shortlisted candidates found to schedule.", "scheduled": []}
        
    # Calculate baseline start time (next working day at 09:00 AM)
    baseline_start = get_baseline_start_time()
    
    # Query database to find the maximum scheduled interview end time across the entire organization
    max_scheduled_end = None
    async for item in interviews_collection.find({"status": "Scheduled"}):
        ts = item.get("interview_timestamp")
        if not ts:
            # Fallback to parsing strings
            ts = parse_date_time_strings(item.get("interview_date", ""), item.get("time_slot", ""))
        
        if ts:
            end_time = ts + timedelta(hours=1)
            if max_scheduled_end is None or end_time > max_scheduled_end:
                max_scheduled_end = end_time
                
    # Next slot starts either at baseline or the last scheduled end time, whichever is later
    current_slot_start = baseline_start
    if max_scheduled_end and max_scheduled_end > baseline_start:
        current_slot_start = max_scheduled_end
        
    # Make sure starting slot is valid
    current_slot_start = get_next_valid_slot(current_slot_start)
    
    scheduled_interviews = []
    
    for applicant_id in applicant_ids:
        # Check if existing interview request exists
        existing = await interviews_collection.find_one({"applicant_id": applicant_id, "job_id": job_id})
        
        formatted_date = current_slot_start.strftime("%A, %B %d, %Y")
        formatted_time = current_slot_start.strftime("%I:%M %p")
        
        update_fields = {
            "applicant_id": applicant_id,
            "job_id": job_id,
            "interview_date": formatted_date,
            "time_slot": formatted_time,
            "interview_timestamp": current_slot_start,
            "mode": "Automated",
            "suggested_slots": [],
            "status": "Scheduled",
            "meeting_link": "https://meet.google.com/interview-room",
            "created_at": datetime.utcnow()
        }
        
        if existing:
            await interviews_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields}
            )
            interview_id = str(existing["_id"])
        else:
            new_int = await interviews_collection.insert_one(update_fields)
            interview_id = str(new_int.inserted_id)
            
        scheduled_interviews.append({
            "interview_id": interview_id,
            "applicant_id": applicant_id,
            "interview_date": formatted_date,
            "time_slot": formatted_time
        })
        
        # Advance slot pointer by 1 hour
        current_slot_start = current_slot_start + timedelta(hours=1)
        current_slot_start = get_next_valid_slot(current_slot_start)
        
    return {
        "message": "Sequential automated scheduling completed successfully.",
        "scheduled": scheduled_interviews
    }
