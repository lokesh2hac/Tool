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
    app_phone = _require_session(request)
    # Get all sessions where app_user_phone matches the logged‑in app phone.
    # If some rows still have NULL, we also include them by matching phone.
    res = supabase.table("telegram_sessions")\
        .select("phone, created_at")\
        .or_(f"app_user_phone.eq.{app_phone},app_user_phone.is.null,phone.eq.{app_phone}")\
        .execute()
    # Deduplicate by phone (in case of duplicates)
    seen = set()
    unique = []
    for row in (res.data or []):
        if row["phone"] not in seen:
            seen.add(row["phone"])
            unique.append(row)
    return unique

@router.post("/active")
async def set_active_session(request: Request, payload: dict):
    app_phone = _require_session(request)
    telegram_phone = payload.get("phone")
    if not telegram_phone:
        raise HTTPException(400, "Missing phone")
    # Verify this phone exists for this app user
    res = supabase.table("telegram_sessions")\
        .select("phone")\
        .or_(f"app_user_phone.eq.{app_phone},phone.eq.{telegram_phone}")\
        .eq("phone", telegram_phone)\
        .execute()
    if not res.data:
        raise HTTPException(404, "Session not found for this user")
    request.session["active_telegram_phone"] = telegram_phone
    return {"active": telegram_phone}

@router.get("/active")
async def get_active_session(request: Request):
    app_phone = _require_session(request)
    active = request.session.get("active_telegram_phone")
    if not active:
        # If no active set, use the app phone (which is a valid session)
        # But check if session exists
        res = supabase.table("telegram_sessions")\
            .select("phone")\
            .eq("phone", app_phone)\
            .execute()
        if res.data:
            active = app_phone
        else:
            # Fallback to first available session for this app user
            res = supabase.table("telegram_sessions")\
                .select("phone")\
                .or_(f"app_user_phone.eq.{app_phone},phone.eq.{app_phone}")\
                .limit(1)\
                .execute()
            if res.data:
                active = res.data[0]["phone"]
    return {"active": active}
