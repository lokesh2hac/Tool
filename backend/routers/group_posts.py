from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from lib import gemini, telegram_client
from lib.supabase_client import supabase

router = APIRouter(tags=["Group Posts"])

def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone

def _get_active_phone(request: Request):
    app_phone = _require_session(request)
    return request.session.get("active_telegram_phone", app_phone)

async def _get_client(request: Request):
    phone = _get_active_phone(request)
    res = supabase.table("telegram_sessions").select("session_string").eq("phone", phone).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="Telegram session not found. Please log in again.")
    session_string = res.data[0]["session_string"]
    client = await telegram_client.get_client_for_phone(phone, session_string)
    return client

@router.get("/generate-message")
async def generate_recruitment_post(
    request: Request,
    brand_name: str = Query("ACE2KING", description="Brand name for the post")
):
    """Generate a unique recruitment post using AI."""
    _require_session(request)
    try:
        message = await gemini.generate_recruitment_post(brand_name)
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate message: {str(e)}")

@router.get("/check-permissions")
async def check_group_permissions(
    request: Request,
    group_username: str = Query(..., description="Group username to check")
):
    """Check if the group allows sending messages."""
    _require_session(request)
    client = await _get_client(request)
    try:
        can_send = await telegram_client.can_send_messages(client, group_username)
        return {"can_send": can_send}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to check permissions: {str(e)}")

class SendPostRequest(BaseModel):
    group_usernames: List[str]
    message: str
    delay_between: float = 2.0

@router.post("/send")
async def send_posts_to_groups(body: SendPostRequest, request: Request):
    """Send the recruitment post to selected groups."""
    _require_session(request)
    client = await _get_client(request)
    results = []
    for username in body.group_usernames:
        try:
            await telegram_client.send_message_to_group(client, username, body.message)
            results.append({"group": username, "success": True})
        except Exception as e:
            results.append({"group": username, "success": False, "error": str(e)})
        await asyncio.sleep(body.delay_between)
    return {"results": results}
