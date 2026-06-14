from fastapi import APIRouter, HTTPException, Body, Depends, File, UploadFile
from app.models import EmployeeModel, AddEmployeeModel
from app.database import employee_collection
import bcrypt
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
from uuid import uuid4
from app.utils.auth import get_current_user
from app.auth import require_admin, require_employee
from app.cloudinary_config import store_cv_and_get_url

# --- 1. ROUTER SABSE PEHLE DEFINE HONA CHAHIYE ---
router = APIRouter()

# --- CONFIGURATION ---
SECRET_KEY = os.getenv("SECRET_KEY", "intellihire_secret_key_2025_fyp_deepanalysis")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- HELPER FUNCTIONS ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- SCHEMAS ---
class LoginSchema(BaseModel):
    email: str
    password: str

# --- API ROUTES ---

# 1. ADD EMPLOYEE (Admin only - creates employee record without password/email)
@router.post("/add")
async def add_employee(employee: AddEmployeeModel = Body(...), current_user=Depends(require_admin)):
    """Admin adds employee with CNIC and employee_code. Employee will complete signup later."""
    # Validate CNIC
    if not employee.cnic or len(employee.cnic) != 13 or not employee.cnic.isdigit():
        raise HTTPException(status_code=400, detail="CNIC must be exactly 13 digits")
    
    # Check if CNIC already exists
    existing_cnic = await employee_collection.find_one({"cnic": employee.cnic})
    if existing_cnic:
        raise HTTPException(status_code=400, detail="CNIC already exists!")
    
    # Check if employee_code already exists
    existing_code = await employee_collection.find_one({"employee_code": employee.employee_code})
    if existing_code:
        raise HTTPException(status_code=400, detail="Employee code already exists!")
    
    # Create employee record (without password and email - will be added during signup)
    emp_data = {
        "employee_code": employee.employee_code,
        "cnic": employee.cnic,
        "full_name": employee.full_name or "",
        "role": employee.role,
        "salary": employee.salary,
        "mobile": employee.mobile,
        "email": "",  # Will be set during signup
        "password": "",  # Will be set during signup
        "joined_at": datetime.utcnow(),
        "paid_leaves_total": 20,
        "paid_leaves_used": 0
    }
    
    new_employee = await employee_collection.insert_one(emp_data)
    return {"message": "Employee added successfully", "id": str(new_employee.inserted_id)}

# 2. SIGNUP API (Employee completes their profile)
@router.post("/signup")
async def signup_employee(employee: EmployeeModel = Body(...)):
    """Employee signup - verifies CNIC and employee_code match existing record, then updates with email/password"""
    # Validate CNIC
    if not employee.cnic or len(employee.cnic) != 13 or not employee.cnic.isdigit():
        raise HTTPException(status_code=400, detail="CNIC must be exactly 13 digits")
    
    # Find existing employee by CNIC and employee_code
    existing_emp = await employee_collection.find_one({
        "cnic": employee.cnic,
        "employee_code": employee.employee_code
    })
    
    if not existing_emp:
        raise HTTPException(
            status_code=403, 
            detail="User not enrolled as employee. Please contact administrator."
        )
    
    # Check if already signed up (has email/password)
    if existing_emp.get("email") and existing_emp.get("password"):
        raise HTTPException(status_code=400, detail="Employee already signed up. Please login instead.")
    
    # Check if email is already used by another employee
    if employee.email:
        email_check = await employee_collection.find_one({
            "email": employee.email,
            "_id": {"$ne": existing_emp["_id"]}
        })
        if email_check:
            raise HTTPException(status_code=400, detail="Email already exists!")
    
    # Hash password using bcrypt directly
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(employee.password.encode('utf-8'), salt).decode('utf-8')
    
    # Update existing employee record with signup details
    update_data = {
        "email": employee.email,
        "password": hashed_password,
        "full_name": employee.full_name,
        "mobile": employee.mobile or existing_emp.get("mobile")
    }
    
    # Update other fields if provided
    if employee.role:
        update_data["role"] = employee.role
    if employee.salary:
        update_data["salary"] = employee.salary
    
    await employee_collection.update_one(
        {"_id": existing_emp["_id"]},
        {"$set": update_data}
    )
    
    return {"message": "Employee signup completed successfully", "id": str(existing_emp["_id"])}

# 2. LOGIN API
@router.post("/login")
async def login_employee(creds: LoginSchema = Body(...)):
    # A. User dhoondo
    user = await employee_collection.find_one({"email": creds.email})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # B. Password match karo using bcrypt directly
    if not user.get("password"):
        raise HTTPException(
            status_code=400, 
            detail="Account exists but signup is not complete. Please signup first."
        )

    if not bcrypt.checkpw(creds.password.encode('utf-8'), user["password"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Incorrect Password")

    # C. JWT Token Generate karo
    access_token = create_access_token(
        data={
            "sub": user["email"], 
            "role": user["role"], 
            "id": str(user["_id"]),
            "employee_code": user.get("employee_code", "")
        }
    )

    # D. Token wapis bhejo
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_role": user.get("role", "Employee"),
        "user_name": user.get("full_name", ""),
        "employee_id": str(user.get("_id")),
        "employee_code": user.get("employee_code", ""),
        "salary": user.get("salary", 0.0),
        "onboarding_completed": user.get("onboarding_completed", False)
    }


# 3. GET ALL EMPLOYEES (Admin view)
@router.get("/all")
async def get_all_employees():

    employees = []
    async for emp in employee_collection.find():
        emp["_id"] = str(emp["_id"])
        # Password ko kabhi expose nahi karna
        emp.pop("password", None)
        employees.append(emp)
    return employees

# --- GET MY PROFILE ---
@router.get("/me")
async def get_my_profile(current_user=Depends(get_current_user)):
    email = current_user.get("sub")
    user = await employee_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["_id"] = str(user["_id"])
    user.pop("password", None)
    return user


@router.get("/{employee_code}")
async def get_employee_by_code(employee_code: str, user=Depends(get_current_user)):
    """Get a single employee by their employee_code."""
    emp = await employee_collection.find_one({"employee_code": employee_code})
    if not emp:
        # try by _id
        try:
            from bson import ObjectId
            emp = await employee_collection.find_one({"_id": ObjectId(employee_code)})
        except Exception:
            emp = None

    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    emp.pop("password", None)
    emp["_id"] = str(emp["_id"])
    return emp

# 4. UPDATE EMPLOYEE (Admin can update employee details)
@router.patch("/{employee_code}")
async def update_employee(employee_code: str, update_data: dict = Body(...), current_user=Depends(require_admin)):

    
    """Update employee details by employee_code."""
    from bson import ObjectId
    
    # Find employee by employee_code first
    emp = await employee_collection.find_one({"employee_code": employee_code})
    if not emp:
        # Try by _id
        try:
            emp = await employee_collection.find_one({"_id": ObjectId(employee_code)})
        except Exception:
            emp = None
    
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow password update through this endpoint (use separate endpoint if needed)
    update_data.pop("password", None)
    update_data.pop("_id", None)  # Don't allow _id update
    
    # Immutable identifiers (admin-only endpoint — salary may be updated here and via payroll save)
    update_data.pop("role", None)
    update_data.pop("cnic", None)
    update_data.pop("employee_code", None)

    if "salary" in update_data:
        try:
            update_data["salary"] = float(update_data["salary"])
        except (TypeError, ValueError):
            update_data["salary"] = 0.0
    
    # Update employee
    result = await employee_collection.update_one(
        {"_id": emp["_id"]},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Return updated employee
    updated_emp = await employee_collection.find_one({"_id": emp["_id"]})
    updated_emp.pop("password", None)
    updated_emp["_id"] = str(updated_emp["_id"])
    return updated_emp

# --- COMPLETE ONBOARDING ---
@router.patch("/onboarding/complete")
async def complete_onboarding(data: dict = Body(...), current_user=Depends(get_current_user)):
    email = current_user.get("sub")
    
    update_fields = {
        "onboarding_completed": True,
        "linkedin_url": data.get("linkedin_url"),
        "bio": data.get("bio"),
        "goals": data.get("goals"),
        "distilled_profile": data.get("distilled_profile"),
        "profile_picture": data.get("profile_picture"),
        "banner_picture": data.get("banner_picture"),
        "cv_url": data.get("cv_url")
    }
    
    # Remove None values
    update_fields = {k: v for k, v in update_fields.items() if v is not None}
    
    result = await employee_collection.update_one(
        {"email": email},
        {"$set": update_fields}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"message": "Onboarding completed successfully"}

# --- UPLOAD CV ---
@router.post("/upload-cv")
async def upload_cv_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    email = current_user.get("sub")
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

        # Save to database for the employee
        await employee_collection.update_one(
            {"email": email},
            {"$set": {"cv_url": cv_url}}
        )

        return {"cv_url": cv_url}
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))