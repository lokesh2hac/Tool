import json
import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from lib import gemini, auto_scan
from lib.supabase_client import supabase
from lib.telegram_client import get_client_for_phone

router = APIRouter(prefix="/auto-scan", tags=["Auto Scan"])


class AutoScanRequest(BaseModel):
    brand_name: str
    gemini_key_id: Optional[str] = None
    gemini_api_key: Optional[str] = None
    model: str = gemini.DEFAULT_GEMINI_MODEL


def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone


def _resolve_gemini_key(gemini_key_id: Optional[str], gemini_api_key: Optional[str], model: str):
    """Set the active Gemini key for this request."""
    if gemini_api_key:
        gemini.set_active_gemini_key(gemini_api_key, model=model)
        return
    if gemini_key_id:
        try:
            res = supabase.table("api_keys").select("api_key").eq("id", gemini_key_id).execute()
            if res.data:
                gemini.set_active_gemini_key(res.data[0]["api_key"], model=model)
        except Exception:
            pass


@router.post("")
async def start_auto_scan(body: AutoScanRequest, request: Request):
    phone = _require_session(request)
    _resolve_gemini_key(body.gemini_key_id, body.gemini_api_key, body.model)

    # Get the Telegram client from the stored session
    # We need the session string; get it from supabase
    try:
        res = supabase.table("telegram_sessions").select("session_string").eq("phone", phone).execute()
        if not res.data:
            raise HTTPException(status_code=401, detail="Telegram session not found. Please log in again.")
        session_string = res.data[0]["session_string"]
        client = await get_client_for_phone(phone, session_string)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Telegram: {str(e)}")

    async def event_generator():
        queue = asyncio.Queue()

        async def progress_callback(update):
            await queue.put(update)

        # Launch the scan in the background
        asyncio.create_task(
            auto_scan.auto_scan(
                client=client,
                brand_name=body.brand_name,
                duration_seconds=300,
                progress_callback=progress_callback
            )
        )

        # Stream events until 'complete'
        while True:
            try:
                update = await asyncio.wait_for(queue.get(), timeout=10.0)
                yield f"data: {json.dumps(update)}\n\n"
                if update.get("step") == "complete":
                    break
            except asyncio.TimeoutError:
                # Send a heartbeat to keep connection alive
                yield f"data: {json.dumps({'step': 'heartbeat', 'message': 'Scanning...'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
