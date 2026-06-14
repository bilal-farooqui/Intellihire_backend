from fastapi import APIRouter, Body, HTTPException, Request
from bson import ObjectId
from datetime import datetime, time
import ipaddress
from app.models import AttendanceModel, DailyAttendanceModel
from app.database import attendance_collection, leave_collection, daily_attendance_collection, settings_collection, wfh_collection

router = APIRouter()

# --- OFFICE NETWORK VALIDATION ---
async def is_authorized_ip(client_ip: str):
    try:
        settings = await settings_collection.find_one({})
        allowed_ips = settings.get("allowed_ips", []) if settings else ["127.0.0.1", "::1"]
        
        # Check against simple IP list
        if client_ip in allowed_ips:
            return True
            
        # Also check if allowed_ips are subnets (e.g. 192.168.1.0/24)
        addr = ipaddress.ip_address(client_ip)
        for subnet in allowed_ips:
            try:
                if addr in ipaddress.ip_network(subnet):
                    return True
            except:
                pass
                
        return False
    except:
        return False

# --- 1. GET TODAY'S STATUS ---
@router.get("/today-status/{employee_id}")
async def get_today_status(employee_id: str):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    record = await daily_attendance_collection.find_one({
        "employee_id": employee_id,
        "date": today
    })
    
    if not record:
        return {"status": "Not Clocked In"}
    
    record["_id"] = str(record["_id"])
    return {
        "status": "Clocked In" if not record.get("time_out") else "Clocked Out",
        "time_in": record.get("time_in"),
        "time_out": record.get("time_out"),
        "ip_address": record.get("ip_address")
    }

# --- 2. MARK ATTENDANCE (Time-in / Time-out) ---
@router.post("/mark")
async def mark_attendance(request: Request, payload: dict = Body(...)):
    employee_id = payload.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="Employee ID is required")
    
    client_ip = request.client.host
    # For local development with '::1', convert to '127.0.0.1'
    if client_ip == "::1": client_ip = "127.0.0.1"

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    is_wfh_approved = False
    wfh_req = await wfh_collection.find_one({
        "employee_id": employee_id,
        "date": today,
        "status": "Approved"
    })
    if wfh_req:
        is_wfh_approved = True

    if not is_wfh_approved and not await is_authorized_ip(client_ip):
         raise HTTPException(status_code=403, detail=f"Outside Network Range ({client_ip})")

    # Check if record exists for today
    existing = await daily_attendance_collection.find_one({
        "employee_id": employee_id,
        "date": today
    })

    if not existing:
        # 1. TIME-IN
        daily_status = "Present"
        if now.time() > time(9, 15):
            daily_status = "Late"
            
        new_record = DailyAttendanceModel(
            employee_id=employee_id,
            date=today,
            time_in=now,
            ip_address=client_ip,
            status=daily_status
        )
        await daily_attendance_collection.insert_one(new_record.dict())
        
        # If Late, increment monthly late_days
        if daily_status == "Late":
            att = await attendance_collection.find_one({"employee_id": employee_id, "month": today.month, "year": today.year})
            if att:
                new_late = att.get("late_days", 0) + 1
                await attendance_collection.update_one({"_id": att["_id"]}, {"$set": {"late_days": new_late}})
            else:
                await attendance_collection.insert_one({
                    "employee_id": employee_id,
                    "month": today.month,
                    "year": today.year,
                    "absent_days": 0,
                    "late_days": 1,
                    "approved_leaves": 0,
                    "paid_leaves": 0,
                    "daily_deduction": 0.0,
                    "unapproved_absence": 0
                })

        return {"message": f"Success: Clocked In ({daily_status})", "time": now.isoformat()}
    
    if existing.get("time_out"):
        # Already clocked out
        raise HTTPException(status_code=400, detail="Target Met: You have already clocked out for today.")

    # 2. TIME-OUT
    time_in = existing.get("time_in")
    duration = now - time_in
    total_hours = round(duration.total_seconds() / 3600, 2)
    
    daily_status = "Present"
    if total_hours < 8:
        daily_status = "Absent (Short Hours)"

    await daily_attendance_collection.update_one(
        {"_id": existing["_id"]},
        {"$set": {
            "time_out": now,
            "total_hours": total_hours,
            "status": daily_status
        }}
    )
    
    # If they worked less than 8 hours, automatically increment their monthly absent_days penalty
    if total_hours < 8:
        att = await attendance_collection.find_one({"employee_id": employee_id, "month": today.month, "year": today.year})
        if att:
            new_absent = att.get("absent_days", 0) + 1
            await attendance_collection.update_one({"_id": att["_id"]}, {"$set": {"absent_days": new_absent}})
        else:
            await attendance_collection.insert_one({
                "employee_id": employee_id,
                "month": today.month,
                "year": today.year,
                "absent_days": 1,
                "late_days": 0,
                "approved_leaves": 0,
                "paid_leaves": 0,
                "daily_deduction": 0.0,
                "unapproved_absence": 1
            })

    return {"message": f"Success: Clocked Out ({total_hours} hrs)", "time": now.isoformat(), "hours": total_hours}

# --- 2.5 AUTO CLOCK-IN ---
@router.post("/auto-clock-in")
async def auto_clock_in(request: Request, payload: dict = Body(...)):
    employee_id = payload.get("employee_id")
    if not employee_id:
        return {"status": "ignored", "detail": "No employee_id"}
        
    client_ip = request.client.host
    if client_ip == "::1": client_ip = "127.0.0.1"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    is_wfh_approved = False
    wfh_req = await wfh_collection.find_one({
        "employee_id": employee_id,
        "date": today,
        "status": "Approved"
    })
    if wfh_req:
        is_wfh_approved = True

    # Silently ignore if not authorized
    if not is_wfh_approved and not await is_authorized_ip(client_ip):
        return {"status": "ignored", "detail": "Outside Network Range"}

    # Check if already clocked in today
    existing = await daily_attendance_collection.find_one({
        "employee_id": employee_id,
        "date": today
    })

    if existing:
        return {"status": "ignored", "detail": "Already Clocked In"}

    # Automatically Time-In
    daily_status = "Present"
    if now.time() > time(9, 15):
        daily_status = "Late"

    new_record = DailyAttendanceModel(
        employee_id=employee_id,
        date=today,
        time_in=now,
        ip_address=client_ip,
        status=daily_status
    )
    await daily_attendance_collection.insert_one(new_record.dict())
    
    # If Late, increment monthly late_days
    if daily_status == "Late":
        att = await attendance_collection.find_one({"employee_id": employee_id, "month": today.month, "year": today.year})
        if att:
            new_late = att.get("late_days", 0) + 1
            await attendance_collection.update_one({"_id": att["_id"]}, {"$set": {"late_days": new_late}})
        else:
            await attendance_collection.insert_one({
                "employee_id": employee_id,
                "month": today.month,
                "year": today.year,
                "absent_days": 0,
                "late_days": 1,
                "approved_leaves": 0,
                "paid_leaves": 0,
                "daily_deduction": 0.0,
                "unapproved_absence": 0
            })
            
    return {"status": "success", "message": f"Auto Clocked In ({daily_status})", "time": now.isoformat()}

# --- 2.6 DEV UTILITY: RESET TODAY'S ATTENDANCE ---
@router.delete("/reset-today")
async def reset_today_attendance():
    """DEV UTILITY: Deletes all attendance records for today to allow re-testing."""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await daily_attendance_collection.delete_many({
        "date": today
    })
    
    return {"message": f"Reset successful. Deleted {result.deleted_count} records for today."}

# --- 3. GET DAILY LOGS (Admin View) ---
@router.get("/daily-logs/{month}/{year}")
async def get_daily_logs(month: int, year: int):
    # Fetch all daily logs for the month/year
    # We filter by 'date' which is midnight. 
    # But wait, date is a datetime object. We need to check month/year.
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    logs = []
    async for log in daily_attendance_collection.find({
        "date": {"$gte": start_date, "$lt": end_date}
    }).sort("date", -1):
        log["_id"] = str(log["_id"])
        logs.append(log)
    
    return logs



@router.get("/all")
async def get_all_attendance(month: int, year: int):
  """Get attendance summary for all employees for a month/year."""
  docs = []
  
  # First, get all approved leaves for this month/year
  approved_leaves_map = {}  # employee_id -> count
  async for leave in leave_collection.find({"status": "Approved"}):
    if leave.get("start_date") and leave.get("employee_id"):
      leave_date = leave["start_date"]
      # Handle both datetime objects and strings
      if isinstance(leave_date, str):
        try:
          leave_date = datetime.fromisoformat(leave_date.replace("Z", "+00:00"))
        except:
          continue
      elif not isinstance(leave_date, datetime):
        continue
      if leave_date.month == month and leave_date.year == year:
        emp_id = leave["employee_id"]
        approved_leaves_map[emp_id] = approved_leaves_map.get(emp_id, 0) + 1
  
  # Now get attendance records and update approved_leaves from leaves database
  async for att in attendance_collection.find({"month": month, "year": year}):
    emp_id = att.get("employee_id")
    approved_count = approved_leaves_map.get(emp_id, 0)
    att["approved_leaves"] = approved_count
    
    # Recalculate unapproved_absence = absent_days - approved_leaves
    absent = att.get("absent_days", 0) or 0
    att["unapproved_absence"] = max(0, absent - approved_count)
    
    att["_id"] = str(att["_id"])
    docs.append(att)
  return docs


@router.get("/employee/{employee_id}")
async def get_employee_attendance(employee_id: str, month: int, year: int):
  """Get single employee's attendance for a given month/year."""
  att = await attendance_collection.find_one(
    {"employee_id": employee_id, "month": month, "year": year}
  )
  if not att:
    return None
  
  # Fetch approved leaves count from leaves database for this month/year
  approved_count = 0
  async for leave in leave_collection.find({
    "employee_id": employee_id,
    "status": "Approved"
  }):
    if leave.get("start_date"):
      leave_date = leave["start_date"]
      # Handle both datetime objects and strings
      if isinstance(leave_date, str):
        try:
          leave_date = datetime.fromisoformat(leave_date.replace("Z", "+00:00"))
        except:
          continue
      elif not isinstance(leave_date, datetime):
        continue
      if leave_date.month == month and leave_date.year == year:
        approved_count += 1
  
  # Update approved_leaves from leaves database
  att["approved_leaves"] = approved_count
  # Recalculate unapproved_absence = absent_days - approved_leaves
  absent = att.get("absent_days", 0) or 0
  att["unapproved_absence"] = max(0, absent - approved_count)
  att["_id"] = str(att["_id"])
  return att


@router.post("/upsert")
async def upsert_attendance(att: AttendanceModel = Body(...)):
  """Create or update monthly attendance for an employee."""
  data = att.dict()
  
  # Fetch approved leaves count from leaves database for this month/year
  approved_count = 0
  async for leave in leave_collection.find({
    "employee_id": att.employee_id,
    "status": "Approved"
  }):
    if leave.get("start_date"):
      leave_date = leave["start_date"]
      # Handle both datetime objects and strings
      if isinstance(leave_date, str):
        try:
          leave_date = datetime.fromisoformat(leave_date.replace("Z", "+00:00"))
        except:
          continue
      elif not isinstance(leave_date, datetime):
        continue
      if leave_date.month == att.month and leave_date.year == att.year:
        approved_count += 1
  
  # Override approved_leaves with count from leaves database
  data['approved_leaves'] = approved_count
  
  # derived fields: unapproved_absence and total_deduction
  absent = data.get('absent_days', 0) or 0
  daily = data.get('daily_deduction', 0) or 0
  
  # unapproved_absence = absent_days - approved_leaves (from leaves database)
  unapproved_absence = max(0, absent - approved_count)
  data['unapproved_absence'] = unapproved_absence
  
  # total_deduction based on unapproved_absence
  data['total_deduction'] = unapproved_absence * daily
  
  # Keep unpaid_days for backward compatibility
  paid = data.get('paid_leaves', 0) or 0
  unpaid = max(0, absent - approved_count - paid)
  data['unpaid_days'] = unpaid
  existing = await attendance_collection.find_one(
    {"employee_id": att.employee_id, "month": att.month, "year": att.year}
  )
  if existing:
    await attendance_collection.update_one(
      {"_id": existing["_id"]},
      {"$set": data},
    )
    return {"message": "Attendance updated"}
  else:
    new_doc = await attendance_collection.insert_one(data)
    return {"message": "Attendance created", "id": str(new_doc.inserted_id)}


