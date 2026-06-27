from fastapi import APIRouter, Request, HTTPException
from typing import List
from lib.supabase_client import supabase

router = APIRouter(prefix="/sessions", tags=["sessions"])

def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone

@router.get("")
async def list_sessions(request: Request) -> List[dict]:
    """List all Telegram sessions saved for this app user."""
    app_phone = _require_session(request)
    res = supabase.table("telegram_sessions")\
        .select("phone, created_at")\
        .eq("app_user_phone", app_phone)\
        .execute()
    return res.data or []

@router.post("/active")
async def set_active_session(request: Request, payload: dict):
    """Set which Telegram phone number to use for this session."""
    app_phone = _require_session(request)
    telegram_phone = payload.get("phone")
    if not telegram_phone:
        raise HTTPException(400, "Missing phone")
    # Verify this phone belongs to this app user
    res = supabase.table("telegram_sessions")\
        .select("phone")\
        .eq("app_user_phone", app_phone)\
        .eq("phone", telegram_phone)\
        .execute()
    if not res.data:
        raise HTTPException(404, "Session not found for this user")
    # Store in session cookie
    request.session["active_telegram_phone"] = telegram_phone
    return {"active": telegram_phone}

@router.get("/active")
async def get_active_session(request: Request):
    app_phone = _require_session(request)
    active = request.session.get("active_telegram_phone")
    if not active:
        # fallback to app phone itself
        active = app_phone
    return {"active": active}
