import json
import asyncio
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from lib import gemini, auto_scan
from lib.supabase_client import supabase
from lib.telegram_client import get_client_for_phone

router = APIRouter(prefix="/auto-scan", tags=["Auto Scan"])


def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone


def _resolve_gemini_key(gemini_key_id: Optional[str], gemini_api_key: Optional[str], model: str):
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


async def _save_candidates(candidates: list):
    """Insert candidates into the candidates table."""
    for c in candidates:
        try:
            row = {
                "telegram_username": c.get("username", ""),
                "display_name": c.get("display_name", ""),
                "message_sample": c.get("sample_message", ""),
                "ai_score": int(c.get("score", 0)),
                "ai_reason": c.get("reason", ""),
                "status": "new",
                "group_id": None,
            }
            supabase.table("candidates").insert(row).execute()
        except Exception as e:
            print(f"Failed to save candidate {c.get('username')}: {e}")


@router.get("")
async def start_auto_scan(
    request: Request,  # 👈 moved to first position
    brand_name: str = Query(..., description="Brand name to search for"),
    model: str = Query(gemini.DEFAULT_GEMINI_MODEL, description="AI model"),
    gemini_key_id: Optional[str] = Query(None, description="Gemini key ID from DB"),
    gemini_api_key: Optional[str] = Query(None, description="Raw Gemini API key"),
):
    phone = _require_session(request)
    _resolve_gemini_key(gemini_key_id, gemini_api_key, model)

    # Get Telegram client
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

        asyncio.create_task(
            auto_scan.auto_scan(
                client=client,
                brand_name=brand_name,
                duration_seconds=300,
                progress_callback=progress_callback,
                save_callback=_save_candidates,
            )
        )

        while True:
            try:
                update = await asyncio.wait_for(queue.get(), timeout=10.0)
                yield f"data: {json.dumps(update)}\n\n"
                if update.get("step") == "complete":
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'step': 'heartbeat', 'message': 'Scanning...'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
