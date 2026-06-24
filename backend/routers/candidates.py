from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from lib import gemini
from lib.supabase_client import supabase

router = APIRouter()


def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone


class Message(BaseModel):
    text: str
    sender_username: Optional[str] = ""
    sender_name: Optional[str] = ""


class AnalyzeRequest(BaseModel):
    group_username: str
    group_id: Optional[str] = None
    messages: List[Message]


@router.post("/analyze")
async def analyze_candidates(body: AnalyzeRequest, request: Request):
    phone = _require_session(request)

    messages_list = [m.dict() for m in body.messages]

    try:
        candidates = await gemini.analyze_candidates(messages_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    saved_candidates = []
    for c in candidates:
        try:
            row = {
                "telegram_username": c.get("username", ""),
                "display_name": c.get("display_name", ""),
                "message_sample": c.get("sample_message", ""),
                "ai_score": int(c.get("score", 0)),
                "ai_reason": c.get("reason", ""),
                "status": "new",
            }
            if body.group_id:
                row["group_id"] = body.group_id
            res = supabase.table("candidates").insert(row).execute()
            if res.data:
                c["db_id"] = res.data[0]["id"]
            saved_candidates.append(c)
        except Exception:
            saved_candidates.append(c)

    return saved_candidates


@router.get("")
async def list_candidates(request: Request):
    phone = _require_session(request)

    try:
        # Get all groups for this phone
        groups_res = supabase.table("scanned_groups").select("id").eq("session_phone", phone).execute()
        group_ids = [g["id"] for g in (groups_res.data or [])]

        if not group_ids:
            return []

        # Get candidates for those groups
        result = supabase.table("candidates").select(
            "id, telegram_username, display_name, message_sample, ai_score, ai_reason, status, group_id, created_at"
        ).in_("group_id", group_ids).order("ai_score", desc=True).execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
