from fastapi import APIRouter, Body, HTTPException
from bson import ObjectId
from datetime import datetime
from app.models import PayrollModel
from app.database import payroll_collection, attendance_collection, leave_collection, employee_collection

router = APIRouter()

# 1. ADMIN: Generate Payroll Preview or Fetch Processed Payroll
@router.get("/generate/{month}/{year}")
async def generate_payroll(month: int, year: int):
    results = []
    
    # Get all employees (exclude applicants)
    employees = []
    async for emp in employee_collection.find({"role": {"$nin": ["Applicant", "applicant"]}}):
        employees.append(emp)
        
    for emp in employees:
        emp_id = emp.get("employee_code")
        base_salary = emp.get("salary", 0.0)
        
        # Check if already processed
        processed_payroll = await payroll_collection.find_one({
            "employee_id": emp_id,
            "month": month,
            "year": year
        })
        
        if processed_payroll:
            processed_payroll["_id"] = str(processed_payroll["_id"])
            processed_payroll["full_name"] = emp.get("full_name")
            results.append(processed_payroll)
            continue
            
        # Calculate Preview
        # Get attendance record
        att = await attendance_collection.find_one({
            "employee_id": emp_id,
            "month": month,
            "year": year
        })
        
        absent_days = att.get("absent_days", 0) if att else 0
        late_days = att.get("late_days", 0) if att else 0
        
        # Calculate approved leaves
        approved_count = 0
        async for leave in leave_collection.find({"employee_id": emp_id, "status": "Approved"}):
            leave_date = leave.get("start_date")
            if isinstance(leave_date, str):
                try:
                    leave_date = datetime.fromisoformat(leave_date.replace("Z", "+00:00"))
                except:
                    continue
            if isinstance(leave_date, datetime) and leave_date.month == month and leave_date.year == year:
                approved_count += 1
                
        unapproved_absence = max(0, absent_days - approved_count)
        daily_deduction = att.get("daily_deduction", 0.0) if att else (base_salary / 22 if base_salary else 0.0)
        penalty_deduction = round((unapproved_absence * daily_deduction) + (late_days * daily_deduction * 0.25), 2)
        final_salary = max(0, base_salary - penalty_deduction)
        
        preview = {
            "employee_id": emp_id,
            "full_name": emp.get("full_name"),
            "month": month,
            "year": year,
            "base_salary": base_salary,
            "unapproved_absences": unapproved_absence,
            "late_days": late_days,
            "daily_deduction_rate": daily_deduction,
            "penalty_deduction": penalty_deduction,
            "bonus": 0.0,
            "final_salary": final_salary,
            "status": "Pending"
        }
        results.append(preview)
        
    return results

# 2. ADMIN: Process / Update Payroll
@router.post("/process")
async def process_payroll(payload: PayrollModel = Body(...)):
    data = payload.dict()
    data["status"] = "Processed"
    data["processed_date"] = datetime.utcnow()
    
    # Recalculate final salary just to be safe
    data["final_salary"] = max(0, data["base_salary"] - data["penalty_deduction"] + data["bonus"])
    
    existing = await payroll_collection.find_one({
        "employee_id": data["employee_id"],
        "month": data["month"],
        "year": data["year"]
    })
    
    if existing:
        await payroll_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": data}
        )
        msg = "Payroll updated successfully"
    else:
        await payroll_collection.insert_one(data)
        msg = "Payroll processed successfully"

    # Keep employee directory in sync: Employees module reads `salary` from employee_collection
    emp_code = data.get("employee_id")
    if emp_code:
        try:
            base = float(data.get("base_salary", 0) or 0)
        except (TypeError, ValueError):
            base = 0.0
        await employee_collection.update_one(
            {"employee_code": emp_code},
            {"$set": {"salary": base}},
        )

    return {"message": msg}

# 3. EMPLOYEE: Get My Payroll
@router.get("/employee/{employee_id}")
async def get_my_payroll(employee_id: str, month: int = None, year: int = None):
    query = {"employee_id": employee_id, "status": "Processed"}
    if month is not None:
        query["month"] = month
    if year is not None:
        query["year"] = year
        
    results = []
    async for p in payroll_collection.find(query).sort([("year", -1), ("month", -1)]):
        p["_id"] = str(p["_id"])
        results.append(p)
    return results
