from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from lib import telegram_client, gemini
from lib.supabase_client import supabase

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
            .order("scanned_at", desc=True) \   # ✅ FIXED: use scanned_at
            .execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/search")
async def search_groups(body: SearchGroupsRequest, request: Request):
    """
    1. Gemini AI expands the keyword into 5 iGaming-specific search terms
    2. Telegram searches each keyword for public groups
    3. Results are deduplicated and returned with keywords_used so frontend can show them
    """
    phone = _get_active_phone(request)
    client = await _get_client(phone)

    # Step 1: Gemini generates smart keywords
    try:
        keywords = await gemini.generate_keywords(body.keyword, body.model or gemini.DEFAULT_GEMINI_MODEL)
    except Exception:
        keywords = [body.keyword]

    # Step 2: Search Telegram for each keyword
    seen: set = set()
    all_groups = []

    for kw in keywords:
        try:
            groups = await telegram_client.search_groups(client, kw, limit=20)
            for g in groups:
                key = g.get("group_username") or g.get("group_title", "")
                if key and key not in seen:
                    seen.add(key)
                    all_groups.append(g)
        except Exception:
            continue

    # Step 3: Save to Supabase (upsert to avoid duplicates) and attach IDs
    saved = []
    for g in all_groups:
        try:
            # Check if already exists for this user
            existing = supabase.table("scanned_groups") \
                .select("id") \
                .eq("session_phone", phone) \
                .eq("group_username", g.get("group_username") or "") \
                .execute()
            if existing.data:
                g["id"] = existing.data[0]["id"]
                # Optionally update member_count
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
