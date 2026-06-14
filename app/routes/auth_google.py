from fastapi import APIRouter, HTTPException, Body
from google.oauth2 import id_token
from google.auth.transport import requests
from app.database import employee_collection
from app.routes.employee_routes import create_access_token
from pydantic import BaseModel
from datetime import datetime
import os

router = APIRouter()

# IMPORTANT: You must set this in your .env file
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

class GoogleLoginSchema(BaseModel):
    token: str

@router.post("/google")
async def login_google(data: GoogleLoginSchema = Body(...)):
    """
    Verifies Google ID Token and logs in/signs up the applicant.
    """
    try:
        # Verify Google Token
        # Note: In a production environment, you should also verify the 'aud' field matches your Client ID
        # idinfo = id_token.verify_oauth2_token(data.token, requests.Request(), GOOGLE_CLIENT_ID)
        
        # For testing purposes, if GOOGLE_CLIENT_ID is not set, we might have issues verifying.
        # But we'll try to verify it properly.
        idinfo = id_token.verify_oauth2_token(data.token, requests.Request())

        # Check if the audience is correct (if provided)
        if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_ID != "YOUR_GOOGLE_CLIENT_ID_HERE":
             if idinfo['aud'] != GOOGLE_CLIENT_ID:
                 raise HTTPException(status_code=400, detail="Token audience mismatch")

        email = idinfo['email']
        name = idinfo.get('name', '')

        # 1. User check in database
        user = await employee_collection.find_one({"email": email})

        if not user:
            # Create new Applicant user automatically
            new_user_data = {
                "full_name": name,
                "email": email,
                "role": "applicant",
                "employee_code": f"APP-{email.split('@')[0]}", # Just a unique code
                "cnic": "0000000000000", # Dummy for applicants login
                "joined_at": datetime.utcnow(),
                "is_google_user": True,
                "onboarding_completed": False
            }
            inserted = await employee_collection.insert_one(new_user_data)
            user = await employee_collection.find_one({"_id": inserted.inserted_id})

        # 2. Issue JWT Token (same as employee login)
        access_token = create_access_token(
            data={"sub": user["email"], "role": user["role"], "id": str(user["_id"])}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_role": user.get("role", "applicant"),
            "user_name": user.get("full_name", ""),
            "employee_id": str(user.get("_id")),
            "email": user.get("email"),
            "onboarding_completed": user.get("onboarding_completed", False)
        }

    except ValueError as e:
        # Invalid token
        print(f"Google Token Validation Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid Google token")
    except Exception as e:
        print(f"General Auth Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
