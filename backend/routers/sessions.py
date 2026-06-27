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
    """Show ALL Telegram sessions from the database."""
    _require_session(request)
    res = supabase.table("telegram_sessions")\
        .select("phone, created_at")\
        .execute()
    # Deduplicate
    seen = set()
    unique = []
    for row in (res.data or []):
        if row["phone"] not in seen:
            seen.add(row["phone"])
            unique.append(row)
    return unique

@router.post("/active")
async def set_active_session(request: Request, payload: dict):
    """Switch to the selected phone number."""
    _require_session(request)
    telegram_phone = payload.get("phone")
    if not telegram_phone:
        raise HTTPException(400, "Missing phone")
    # Verify the phone exists
    res = supabase.table("telegram_sessions")\
        .select("phone")\
        .eq("phone", telegram_phone)\
        .execute()
    if not res.data:
        raise HTTPException(404, "Session not found")
    # Store in session cookie
    request.session["active_telegram_phone"] = telegram_phone
    return {"active": telegram_phone}

@router.get("/active")
async def get_active_session(request: Request):
    """Return the currently active phone."""
    _require_session(request)
    active = request.session.get("active_telegram_phone")
    if not active:
        # Default: pick the first session from DB
        res = supabase.table("telegram_sessions")\
            .select("phone")\
            .limit(1)\
            .execute()
        if res.data:
            active = res.data[0]["phone"]
            request.session["active_telegram_phone"] = active
    return {"active": active}
