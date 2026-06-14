from fastapi import APIRouter, HTTPException, Body
from app.models import WFHRequestModel
from app.database import wfh_collection
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# 1. EMPLOYEE: Request WFH
@router.post("/request")
async def request_wfh(wfh_data: WFHRequestModel = Body(...)):
    # Convert date to datetime if it's a string
    data_dict = wfh_data.dict()
    
    # Optional: ensure date is midnight to avoid time matching issues
    if isinstance(data_dict['date'], datetime):
        data_dict['date'] = data_dict['date'].replace(hour=0, minute=0, second=0, microsecond=0)
        
    result = await wfh_collection.insert_one(data_dict)
    return {"message": "WFH Request submitted successfully", "id": str(result.inserted_id)}

# 2. EMPLOYEE: Get My WFH Requests
@router.get("/employee/{employee_id}")
async def get_my_wfh(employee_id: str):
    requests = []
    async for req in wfh_collection.find({"employee_id": employee_id}).sort("date", -1):
        req["_id"] = str(req["_id"])
        requests.append(req)
    return requests

# 3. ADMIN/HR: Get All WFH Requests
@router.get("/all")
async def get_all_wfh():
    requests = []
    async for req in wfh_collection.find({}).sort("date", -1):
        req["_id"] = str(req["_id"])
        requests.append(req)
    return requests

# 4. ADMIN/HR: Approve / Reject WFH
@router.patch("/status/{request_id}")
async def update_wfh_status(request_id: str, payload: dict = Body(...)):
    new_status = payload.get("status")
    admin_comments = payload.get("admin_comments", "")
    
    if new_status not in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    result = await wfh_collection.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": new_status, "admin_comments": admin_comments}}
    )
    
    if result.modified_count == 1:
        return {"message": f"WFH Request {new_status}"}
    raise HTTPException(status_code=404, detail="Request not found")
