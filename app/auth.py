from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

import os
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
ALGORITHM = "HS256"

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(current_user=Depends(get_current_user)):
    if current_user.get("role").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return current_user


def require_employee(current_user=Depends(get_current_user)):
    if current_user.get("role").lower() != "employee":
        raise HTTPException(status_code=403, detail="Employees only")
    return current_user