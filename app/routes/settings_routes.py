from fastapi import APIRouter, Body, HTTPException, Request
from app.models import SettingsModel
from app.database import settings_collection

router = APIRouter()

@router.get("/")
async def get_settings():
    """Get the current settings (including allowed IPs)."""
    settings = await settings_collection.find_one({})
    if not settings:
        # If no settings exist, return default
        return {"allowed_ips": ["127.0.0.1", "::1"]}
    settings["_id"] = str(settings["_id"])
    return settings

@router.put("/")
async def update_settings(payload: SettingsModel = Body(...)):
    """Update settings (allowed IPs)."""
    settings = await settings_collection.find_one({})
    
    if settings:
        await settings_collection.update_one(
            {"_id": settings["_id"]},
            {"$set": {"allowed_ips": payload.allowed_ips}}
        )
    else:
        await settings_collection.insert_one(payload.dict())
        
    return {"message": "Settings updated successfully", "allowed_ips": payload.allowed_ips}

@router.get("/my-ip")
async def get_my_ip(request: Request):
    """Utility to return the requester's IP."""
    client_ip = request.client.host
    if client_ip == "::1":
        client_ip = "127.0.0.1"
    
    # Check headers for real IP if behind a proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        
    return {"ip": client_ip}
