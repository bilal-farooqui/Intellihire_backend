from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
load_dotenv()

security = HTTPBearer(auto_error=False)

# Consistent fallback with employee_routes.py
SECRET_KEY = os.getenv("SECRET_KEY", "intellihire_secret_key_2025_fyp_deepanalysis")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")