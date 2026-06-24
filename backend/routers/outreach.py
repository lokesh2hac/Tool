from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from lib import telegram_client
from lib.supabase_client import supabase

router = APIRouter()


def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone


async def _get_client(phone: str):
    if phone in telegram_client.active_clients:
        client = telegram_client.active_clients[phone]
        if client.is_connected():
            return client

    result = supabase.table("telegram_sessions").select("session_string").eq("phone", phone).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Session not found. Please log in again.")
    session_string = result.data[0]["session_string"]
    client = await telegram_client.get_client_for_phone(phone, session_string)
    return client


class SendOutreachRequest(BaseModel):
    candidate_username: str
    message: str
    candidate_id: Optional[str] = None
    group_source: Optional[str] = None


@router.post("/send")
async def send_outreach(body: SendOutreachRequest, request: Request):
    phone = _require_session(request)
    client = await _get_client(phone)

    username = body.candidate_username.lstrip("@")

    try:
        await telegram_client.send_message(client, username, body.message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        log_row = {
            "candidate_username": body.candidate_username,
            "message_sent": body.message,
            "sent_by_phone": phone,
        }
        if body.candidate_id:
            log_row["candidate_id"] = body.candidate_id
        if body.group_source:
            log_row["group_source"] = body.group_source
        supabase.table("outreach_logs").insert(log_row).execute()
    except Exception:
        pass

    # Update candidate status
    if body.candidate_id:
        try:
            supabase.table("candidates").update({"status": "contacted"}).eq("id", body.candidate_id).execute()
        except Exception:
            pass

    return {"success": True}


@router.get("/history")
async def outreach_history(request: Request):
    phone = _require_session(request)

    try:
        result = supabase.table("outreach_logs").select("*").eq("sent_by_phone", phone).order("sent_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
