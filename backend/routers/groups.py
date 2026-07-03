from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from lib import telegram_client, gemini
from lib.supabase_client import supabase
import asyncio

router = APIRouter()


def _require_phone(request: Request) -> str:
    """Get app phone from session. Raise 401 if not logged in."""
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated. Please login again.")
    return phone


def _get_active_phone(request: Request) -> str:
    """Get the active Telegram phone (from session) or fallback to app phone."""
    app_phone = _require_phone(request)
    return request.session.get("active_telegram_phone", app_phone)


async def _get_client(phone: str):
    """Get active Telegram client, or reconnect from Supabase session string."""
    # Try in-memory first
    if phone in telegram_client.active_clients:
        client = telegram_client.active_clients[phone]
        if client.is_connected():
            return client

    # Reconnect from saved session in Supabase
    try:
        result = supabase.table("telegram_sessions").select("session_string").eq("phone", phone).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not result.data:
        raise HTTPException(status_code=401, detail=f"Session not found for {phone}. Please login again.")

    session_string = result.data[0]["session_string"]
    client = await telegram_client.get_client_for_phone(phone, session_string)
    return client


class SearchGroupsRequest(BaseModel):
    keyword: str
    model: Optional[str] = gemini.DEFAULT_GEMINI_MODEL


class MessagesRequest(BaseModel):
    group_username: str


@router.get("")
async def list_scanned_groups(request: Request):
    """
    List all groups previously scanned by this user (linked to active phone).
    """
    phone = _get_active_phone(request)
    try:
        result = supabase.table("scanned_groups") \
            .select("*") \
            .eq("session_phone", phone) \
            .order("scanned_at", desc=True) \
            .execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/search")
async def search_groups(body: SearchGroupsRequest, request: Request):
    """
    1. Gemini AI expands the keyword into search terms
    2. Telegram searches each keyword for public groups
    3. Filters: only supergroups with a username AND where sending is allowed
    4. Saves only the filtered groups
    """
    phone = _get_active_phone(request)
    client = await _get_client(phone)

    # Generate keywords
    try:
        keywords = await gemini.generate_keywords(body.keyword, body.model or gemini.DEFAULT_GEMINI_MODEL)
    except Exception:
        keywords = [body.keyword]

    seen = set()
    all_groups = []
    filtered_restricted = 0

    for kw in keywords:
        try:
            groups = await telegram_client.search_groups(client, kw, limit=20)
            for g in groups:
                key = g.get("group_username") or g.get("group_title", "")
                if key and key not in seen:
                    seen.add(key)
                    # 👇 Check if we can send messages in this group
                    try:
                        can_send = await telegram_client.can_send_messages(client, g["group_username"])
                        if not can_send:
                            filtered_restricted += 1
                            continue  # skip restricted groups
                    except Exception:
                        filtered_restricted += 1
                        continue
                    all_groups.append(g)
        except Exception:
            continue

    # Save only the filtered groups
    saved = []
    for g in all_groups:
        try:
            existing = supabase.table("scanned_groups") \
                .select("id") \
                .eq("session_phone", phone) \
                .eq("group_username", g.get("group_username") or "") \
                .execute()
            if existing.data:
                g["id"] = existing.data[0]["id"]
                supabase.table("scanned_groups") \
                    .update({"member_count": g.get("member_count", 0)}) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
            else:
                res = supabase.table("scanned_groups").insert({
                    "session_phone": phone,
                    "group_username": g.get("group_username") or "",
                    "group_title": g.get("group_title", ""),
                    "member_count": g.get("member_count", 0),
                    "keyword": body.keyword,
                }).execute()
                if res.data:
                    g["id"] = res.data[0]["id"]
        except Exception:
            pass
        saved.append(g)

    return {
        "groups": saved,
        "keywords_used": keywords,
        "total": len(saved),
        "filtered_restricted": filtered_restricted,   # 👈 new
    }


@router.post("/messages")
async def get_messages(body: MessagesRequest, request: Request):
    phone = _get_active_phone(request)
    client = await _get_client(phone)

    try:
        result = await telegram_client.get_messages(client, body.group_username, limit=100)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
