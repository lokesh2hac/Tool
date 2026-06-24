from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from lib import telegram_client, gemini
from lib.supabase_client import supabase

router = APIRouter()


def _require_phone(request: Request) -> str:
    """Get phone from session. Raise 401 if not logged in."""
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated. Please login again.")
    return phone


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
        raise HTTPException(status_code=401, detail="Session not found. Please login again.")

    session_string = result.data[0]["session_string"]
    client = await telegram_client.get_client_for_phone(phone, session_string)
    return client


class SearchGroupsRequest(BaseModel):
    keyword: str


class MessagesRequest(BaseModel):
    group_username: str


@router.post("/search")
async def search_groups(body: SearchGroupsRequest, request: Request):
    """
    1. Gemini AI expands the keyword into 5 iGaming-specific search terms
    2. Telegram searches each keyword for public groups
    3. Results are deduplicated and returned with keywords_used so frontend can show them
    """
    phone = _require_phone(request)
    client = await _get_client(phone)

    # Step 1: Gemini generates smart keywords
    try:
        keywords = await gemini.generate_keywords(body.keyword)
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

    # Step 3: Save to Supabase and attach IDs
    saved = []
    for g in all_groups:
        try:
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
    phone = _require_phone(request)
    client = await _get_client(phone)

    try:
        result = await telegram_client.get_messages(client, body.group_username, limit=100)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
