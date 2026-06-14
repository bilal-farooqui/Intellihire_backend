from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# ============================
# 0. SETTINGS SCHEMA
# ============================
class SettingsModel(BaseModel):
    allowed_ips: List[str] = Field(default=["127.0.0.1", "::1"])

# ============================
# 1. EMPLOYEE SCHEMA (Users)
# ============================
class EmployeeModel(BaseModel):
    full_name: str = Field(...)
    email: EmailStr = Field(...)
    password: str = Field(...)
    employee_code: str = Field(..., min_length=4, description="Unique ID provided by HR")
    cnic: str = Field(..., min_length=13, max_length=13, description="CNIC number (13 digits, unique)")
    role: str = Field(default="Employee")  # Admin, HR, Employee
    salary: float = Field(default=0.0)
    mobile: Optional[str] = Field(default=None, description="Mobile number")
    # Joining date aur Paid leaves track karne ke liye
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    paid_leaves_total: int = Field(default=20)
    paid_leaves_used: int = Field(default=0)
    
    # Onboarding & Professional Profile (Mainly for Applicants)
    onboarding_completed: bool = Field(default=False)
    linkedin_url: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None)
    profile_picture: Optional[str] = Field(default=None) # URL
    banner_picture: Optional[str] = Field(default=None) # URL
    goals: Optional[str] = Field(default=None)
    distilled_profile: Optional[dict] = Field(default=None)
    cv_url: Optional[str] = Field(default=None)

# Model for Admin to add employee (without password/email initially)
class AddEmployeeModel(BaseModel):
    employee_code: str = Field(..., min_length=4, description="Unique ID provided by HR")
    cnic: str = Field(..., min_length=13, max_length=13, description="CNIC number (13 digits, unique)")
    full_name: Optional[str] = Field(default=None)
    role: str = Field(default="Employee")
    salary: float = Field(default=0.0)
    mobile: Optional[str] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Ali Raza",
                "email": "ali@company.com",
                "password": "strongpassword",
                "employee_code": "EMP001",
                "cnic": "1234567890123",
                "role": "Employee",
                "salary": 75000
            }
        }

# ============================
# 2. JOB OPENING SCHEMA
# ============================
class JobModel(BaseModel):
    title: str = Field(...)  # e.g., Senior React Developer
    description: str = Field(...)
    requirements: List[str] = Field(default=[])  # e.g., ["Python", "FastAPI"]
    location: str = Field(default="Karachi")
    salary_range: str = Field(default="Not Disclosed")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Backend Developer",
                "description": "Need an expert in FastAPI",
                "requirements": ["Python", "MongoDB", "AWS"],
                "location": "Lahore"
            }
        }

# ============================
# 3. JOB APPLICATION SCHEMA (CVs)
# ============================
class ApplicationModel(BaseModel):
    job_id: str = Field(...)  # Kis job ke liye apply kiya
    candidate_name: str = Field(...)
    candidate_email: EmailStr = Field(...)
    cv_url: str = Field(...)  # Cloudinary ka link ayega yahan
    ai_score: int = Field(default=0)  # AI jo score degi (0-100)
    ai_reasoning: str = Field(default="")  # AI ka remarks
    status: str = Field(default="Pending")  # Pending, Shortlisted, Rejected
    applied_at: datetime = Field(default_factory=datetime.utcnow)

# ============================
# 4. LEAVE REQUEST SCHEMA
# ============================
class LeaveModel(BaseModel):
    employee_id: str = Field(...)  # Kon chutti mang raha hai
    start_date: datetime = Field(...)
    end_date: datetime = Field(...)
    reason: str = Field(...)
    leave_type: str = Field(default="Casual")  # Sick, Casual, Annual
    status: str = Field(default="Pending")  # Pending, Approved, Rejected
    admin_comments: Optional[str] = None


# ============================
# 5. ATTENDANCE SUMMARY (per month)
# ============================
class AttendanceModel(BaseModel):
    employee_id: str = Field(...)  # employee_code
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000)
    absent_days: int = Field(default=0)
    late_days: int = Field(default=0)
    approved_leaves: int = Field(default=0)  # Auto-calculated from leaves database (Approved status only)
    paid_leaves: int = Field(default=0)  # Deprecated - not used in calculation
    daily_deduction: float = Field(default=0.0)
    unapproved_absence: int = Field(default=0)  # absent_days - approved_leaves (from leaves database)

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "month": 5,
                "year": 2025,
                "absent_days": 3,
                "approved_leaves": 1,
                "paid_leaves": 1,
                "daily_deduction": 2500.0,
            }
        }

# ============================
# 6. DAILY ATTENDANCE (Time-in/Time-out)
# ============================
class DailyAttendanceModel(BaseModel):
    employee_id: str = Field(...)
    date: datetime = Field(...) # Normalized to midnight
    time_in: datetime = Field(...)
    time_out: Optional[datetime] = Field(default=None)
    ip_address: str = Field(...)
    status: str = Field(default="Present") # Present, Late, Absent
    total_hours: float = Field(default=0.0)

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "date": "2025-05-20T00:00:00",
                "time_in": "2025-05-20T09:00:00",
                "ip_address": "192.168.1.10",
                "status": "Present"
            }
        }

# ============================
# 7. WFH REQUEST SCHEMA
# ============================
class WFHRequestModel(BaseModel):
    employee_id: str = Field(...)
    date: datetime = Field(...)
    reason: str = Field(...)
    status: str = Field(default="Pending") # Pending, Approved, Rejected
    admin_comments: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ============================
# 8. PAYROLL SCHEMA
# ============================
class PayrollModel(BaseModel):
    employee_id: str = Field(...)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000)
    base_salary: float = Field(default=0.0)
    unapproved_absences: int = Field(default=0)
    late_days: int = Field(default=0)
    daily_deduction_rate: float = Field(default=0.0)
    penalty_deduction: float = Field(default=0.0)
    bonus: float = Field(default=0.0)
    final_salary: float = Field(default=0.0)
    status: str = Field(default="Pending") # Pending, Processed
    processed_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ============================
# 9. EXTRA MODULES (Projects, Timesheets, Messages)
# ============================

class ProjectModel(BaseModel):
    name: str = Field(...)
    status: str = Field(default="Active") # Active, On hold, Done
    lead: str = Field(default="Unassigned")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TimeSheetModel(BaseModel):
    employee_code: str = Field(...)
    week: str = Field(...) # e.g., "2026-W16"
    hours_logged: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class MessageModel(BaseModel):
    subject: str = Field(...)
    preview: str = Field(...)
    from_sender: str = Field(default="You")
    read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InterviewModel(BaseModel):
    applicant_id: str = Field(...)  # Ref: User email or code
    job_id: str = Field(...)        # Ref: Job ID
    interview_date: Optional[str] = None  # Confirmed date (formatted string or ISO)
    time_slot: Optional[str] = None       # Confirmed timeslot (e.g. "03:00 PM")
    interview_timestamp: Optional[datetime] = None  # Chronological datetime for calendar view
    mode: str = Field(default="Manual")  # Manual or Automated
    suggested_slots: List[str] = Field(default=[])  # Suggested slot options
    status: str = Field(default="Awaiting_Scheduling")  # Awaiting_Scheduling, Scheduled, Completed, Cancelled
    meeting_link: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)