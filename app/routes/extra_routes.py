from fastapi import APIRouter, Body, HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from app.models import ProjectModel, TimeSheetModel, MessageModel
from app.database import projects_collection, timesheets_collection, messages_collection, daily_attendance_collection

router = APIRouter()

# ============================
# PROJECTS
# ============================

@router.get("/projects")
async def get_all_projects():
    results = []
    async for p in projects_collection.find().sort("updated_at", -1):
        p["_id"] = str(p["_id"])
        results.append(p)
    return results

@router.post("/projects")
async def create_project(payload: ProjectModel = Body(...)):
    new_doc = await projects_collection.insert_one(payload.dict())
    return {"message": "Project created", "id": str(new_doc.inserted_id)}

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    await projects_collection.delete_one({"_id": ObjectId(project_id)})
    return {"message": "Project deleted"}


# ============================
# TIME SHEETS
# ============================

@router.get("/timesheets/{week}")
async def get_timesheets(week: str):
    results = {}
    try:
        # week format: "2026-W16"
        # %G is ISO year, %V is ISO week, %u is weekday (1=Monday)
        start_date = datetime.strptime(f"{week}-1", "%G-W%V-%u")
        end_date = start_date + timedelta(days=7)
    except Exception as e:
        return {} # Invalid week format fallback

    # Dynamically sum total_hours from daily_attendance for the week
    async for att in daily_attendance_collection.find({
        "date": {"$gte": start_date, "$lt": end_date}
    }):
        emp_id = att.get("employee_id")
        hours = att.get("total_hours", 0.0)
        results[emp_id] = round(results.get(emp_id, 0.0) + hours, 2)
        
    return results


# ============================
# MESSAGES
# ============================

@router.get("/messages")
async def get_messages():
    results = []
    async for m in messages_collection.find().sort("created_at", -1):
        m["_id"] = str(m["_id"])
        results.append(m)
    return results

@router.post("/messages")
async def create_message(payload: MessageModel = Body(...)):
    data = payload.dict()
    data["created_at"] = datetime.utcnow()
    new_doc = await messages_collection.insert_one(data)
    return {"message": "Message created", "id": str(new_doc.inserted_id)}

@router.patch("/messages/{message_id}/read")
async def mark_message_read(message_id: str):
    await messages_collection.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"read": True}}
    )
    return {"message": "Message marked as read"}
