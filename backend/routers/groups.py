from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from lib import telegram_client, gemini
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

    # Reconnect from Supabase session
    result = supabase.table("telegram_sessions").select("session_string").eq("phone", phone).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Session not found. Please log in again.")
    session_string = result.data[0]["session_string"]
    client = await telegram_client.get_client_for_phone(phone, session_string)
    return client


class SearchGroupsRequest(BaseModel):
    keyword: str


class MessagesRequest(BaseModel):
    group_username: str


@router.post("/search")
async def search_groups(body: SearchGroupsRequest, request: Request):
    phone = _require_session(request)
    client = await _get_client(phone)

    try:
        keywords = await gemini.generate_keywords(body.keyword)
    except Exception:
        keywords = [body.keyword]

    seen_usernames: set = set()
    all_groups = []

    for kw in keywords:
        try:
            groups = await telegram_client.search_groups(client, kw, limit=20)
            for g in groups:
                key = g.get("group_username") or g.get("group_title")
                if key and key not in seen_usernames:
                    seen_usernames.add(key)
                    all_groups.append(g)
        except Exception:
            continue

    # Save to Supabase
    saved = []
    for g in all_groups:
        try:
            res = supabase.table("scanned_groups").insert({
                "session_phone": phone,
                "group_username": g.get("group_username"),
                "group_title": g.get("group_title", ""),
                "member_count": g.get("member_count", 0),
                "keyword": body.keyword,
            }).execute()
            if res.data:
                g["id"] = res.data[0]["id"]
            saved.append(g)
        except Exception:
            saved.append(g)

    return saved


@router.post("/messages")
async def get_messages(body: MessagesRequest, request: Request):
    phone = _require_session(request)
    client = await _get_client(phone)

    try:
        result = await telegram_client.get_messages(client, body.group_username, limit=100)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
