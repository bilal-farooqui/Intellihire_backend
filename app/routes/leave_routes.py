from fastapi import APIRouter, Body, HTTPException, Depends
from bson import ObjectId
from app.models import LeaveModel
from app.database import leave_collection, employee_collection, client
from app.auth import require_admin, require_employee

router = APIRouter()


# 1. REQUEST LEAVE (EMPLOYEE ONLY)
@router.post("/request")
async def request_leave(
    leave: LeaveModel = Body(...),
    current_user=Depends(require_employee)
):
    # 🔐 Ensure employee can only create their own leave
    # 🔐 Use employee_code from token for consistency
    leave.employee_id = current_user.get("employee_code")

    # Dynamic remaining leaves validation & policy validation
    duration = (leave.end_date - leave.start_date).days + 1
    
    employee = await employee_collection.find_one({"employee_code": leave.employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    total_allocation = employee.get("paid_leaves_total", 10)
    used_leaves = employee.get("paid_leaves_used", 0)
    remaining_leaves = total_allocation - used_leaves

    # Auto-Rejection Rule: Exceeds remaining balance OR global annual cap (10 days)
    if duration > remaining_leaves or duration > 10:
        leave.status = "Rejected"
        leave.admin_comments = "Auto-Rejected: Requested days exceed the available annual leave balance."
        new_leave = await leave_collection.insert_one(leave.dict())
        return {
            "message": "Auto-Rejected: Requested days exceed the available annual leave balance.",
            "id": str(new_leave.inserted_id),
            "status": "Rejected",
            "auto_rejected": True
        }

    new_leave = await leave_collection.insert_one(leave.dict())
    return {"message": "Leave Requested", "id": str(new_leave.inserted_id)}


# 2. GET MY LEAVES (EMPLOYEE ONLY)
@router.get("/employee/{employee_id}")
async def get_my_leaves(
    employee_id: str,
    current_user=Depends(require_employee)
):
    # 🔐 Prevent accessing someone else's data
    # 🔐 Verify ownership using employee_code
    if current_user.get("employee_code") != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    leaves = []
    async for leave in leave_collection.find({"employee_id": employee_id}):
        leave["_id"] = str(leave["_id"])
        leaves.append(leave)
    return leaves


# 3. GET ALL LEAVES (ADMIN ONLY)
@router.get("/all")
async def get_all_leaves(current_user=Depends(require_admin)):
    leaves = []
    async for leave in leave_collection.find():
        leave["_id"] = str(leave["_id"])
        leaves.append(leave)
    return leaves


# 4. UPDATE LEAVE STATUS (ADMIN ONLY)
@router.patch("/status/{leave_id}")
async def update_leave_status(
    leave_id: str,
    payload: dict = Body(...),
    current_user=Depends(require_admin)
):
    status = payload.get("status")
    if status not in {"Pending", "Approved", "Rejected", "Unapproved"}:
        raise HTTPException(status_code=400, detail="Invalid status value")

    update_data = {"status": status}
    admin_comment = payload.get("admin_comments")
    if admin_comment is not None:
        update_data["admin_comments"] = admin_comment

    try:
        obj_id = ObjectId(leave_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid leave id")

    existing = await leave_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Leave not found")

    current = (existing.get("status") or "").strip().lower()
    if current in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="This leave has already been approved or rejected and cannot be changed.",
        )

    # If status is being updated to Approved, atomically check and update the user's used leaves balance
    if status == "Approved":
        start = existing["start_date"]
        end = existing["end_date"]
        duration = (end - start).days + 1
        employee_code = existing["employee_id"]

        transaction_success = False
        try:
            # 1. Try to use MongoDB session/transaction
            async with await client.start_session() as session:
                async with session.start_transaction():
                    emp = await employee_collection.find_one(
                        {"employee_code": employee_code},
                        session=session
                    )
                    if not emp:
                        raise HTTPException(status_code=404, detail="Employee not found")
                    
                    total = emp.get("paid_leaves_total", 10)
                    used = emp.get("paid_leaves_used", 0)
                    if used + duration > total:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Approval failed: Leave duration ({duration} days) exceeds remaining balance ({total - used} days)"
                        )

                    # Update employee record
                    await employee_collection.update_one(
                        {"employee_code": employee_code},
                        {"$inc": {"paid_leaves_used": duration}},
                        session=session
                    )

                    # Update leave record
                    await leave_collection.update_one(
                        {"_id": obj_id},
                        {"$set": update_data},
                        session=session
                    )
                    transaction_success = True
        except Exception as tx_err:
            if isinstance(tx_err, HTTPException):
                raise tx_err
            print(f"Transaction failed, falling back to atomic operators: {tx_err}")

        # 2. Fallback to atomic operations if transactions are unsupported (standalone MongoDB)
        if not transaction_success:
            emp = await employee_collection.find_one({"employee_code": employee_code})
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            total = emp.get("paid_leaves_total", 10)
            used = emp.get("paid_leaves_used", 0)
            if used + duration > total:
                raise HTTPException(
                    status_code=400,
                    detail=f"Approval failed: Leave duration ({duration} days) exceeds remaining balance ({total - used} days)"
                )

            # Atomic query-based guard update on employee collection
            update_res = await employee_collection.update_one(
                {
                    "employee_code": employee_code,
                    "$expr": {
                        "$lte": [
                            {"$add": ["$paid_leaves_used", duration]},
                            "$paid_leaves_total"
                        ]
                    }
                },
                {"$inc": {"paid_leaves_used": duration}}
            )
            if update_res.modified_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Approval failed: Concurrent update or insufficient leave balance."
                )

            # Update leave status
            await leave_collection.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )

    else:
        # Standard status update (for non-Approved states)
        result = await leave_collection.update_one(
            {"_id": obj_id},
            {"$set": update_data},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Leave not found")

    return {"message": "Status updated", "status": status}