from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from lib import gemini
from lib.gemini import GeminiRateLimitError
from lib.supabase_client import supabase

router = APIRouter()


def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone


def _resolve_gemini_key(
    gemini_key_id: Optional[str],
    gemini_api_key: Optional[str],
    model: str = gemini.DEFAULT_GEMINI_MODEL,
) -> None:
    """
    Set the active Gemini key for this request.
    If gemini_api_key is provided directly, use it.
    If only gemini_key_id is provided, look up the actual key from the database.
    """
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


class Message(BaseModel):
    text: str
    sender_username: Optional[str] = ""
    sender_name: Optional[str] = ""


class AnalyzeRequest(BaseModel):
    group_username: str
    group_id: Optional[str] = None
    messages: List[Message]
    gemini_key_id: Optional[str] = None
    gemini_api_key: Optional[str] = None
    model: str = gemini.DEFAULT_GEMINI_MODEL


class BulkAnalyzeGroup(BaseModel):
    group_username: str
    group_id: Optional[str] = None
    messages: List[Message]


class BulkAnalyzeRequest(BaseModel):
    groups: List[BulkAnalyzeGroup]
    gemini_key_id: Optional[str] = None
    gemini_api_key: Optional[str] = None
    model: str = gemini.DEFAULT_GEMINI_MODEL


@router.post("/analyze")
async def analyze_candidates(body: AnalyzeRequest, request: Request):
    """Analyze a single group's messages."""
    _require_session(request)

    _resolve_gemini_key(body.gemini_key_id, body.gemini_api_key, body.model)

    messages_list = [m.dict() for m in body.messages]

    try:
        candidates = await gemini.analyze_candidates(
            messages_list,
            key_id=body.gemini_key_id,
            model=body.model,
        )
    except GeminiRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={"rate_limited": True, "key_id": e.key_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return await _save_candidates(candidates, body.group_id)


@router.post("/analyze-bulk")
async def analyze_bulk(body: BulkAnalyzeRequest, request: Request):
    """
    Analyze multiple groups sequentially.
    Returns per-group results + summary stats.
    Failed groups are skipped, successful ones returned.
    """
    _require_session(request)

    if not body.groups:
        raise HTTPException(status_code=400, detail="No groups provided")

    _resolve_gemini_key(body.gemini_key_id, body.gemini_api_key, body.model)

    all_candidates = []
    success_count = 0
    fail_count = 0
    errors = []

    for grp in body.groups:
        # Dedupe + clean messages
        messages_list = [
            m.dict() for m in grp.messages
            if m.text and m.text.strip()
        ]

        if not messages_list:
            fail_count += 1
            errors.append({"group": grp.group_username, "error": "No valid messages"})
            continue

        try:
            candidates = await gemini.analyze_candidates(
                messages_list,
                key_id=body.gemini_key_id,
                model=body.model,
            )
            saved = await _save_candidates(candidates, grp.group_id)
            for c in saved:
                c["source_group"] = grp.group_username
            all_candidates.extend(saved)
            success_count += 1
        except GeminiRateLimitError as e:
            raise HTTPException(
                status_code=429,
                detail={"rate_limited": True, "key_id": e.key_id},
            )
        except Exception as e:
            fail_count += 1
            errors.append({"group": grp.group_username, "error": str(e)})
            continue

    # Sort final list: Indian first, then by score
    all_candidates.sort(
        key=lambda x: (
            0 if x.get("is_indian_likely") else 1,
            -int(x.get("score", 0))
        )
    )

    return {
        "candidates": all_candidates,
        "summary": {
            "total_groups": len(body.groups),
            "success": success_count,
            "failed": fail_count,
            "total_candidates": len(all_candidates),
            "errors": errors,
        }
    }


async def _save_candidates(candidates: list, group_id: Optional[str]) -> list:
    """Save candidates to Supabase and return enriched list."""
    saved = []
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
            if group_id:
                row["group_id"] = group_id
            res = supabase.table("candidates").insert(row).execute()
            if res.data:
                c["db_id"] = res.data[0]["id"]
            saved.append(c)
        except Exception:
            saved.append(c)
    return saved


@router.get("")
async def list_candidates(request: Request):
    phone = _require_session(request)

    try:
        groups_res = supabase.table("scanned_groups").select("id").eq("session_phone", phone).execute()
        group_ids = [g["id"] for g in (groups_res.data or [])]

        if not group_ids:
            return []

        result = supabase.table("candidates").select(
            "id, telegram_username, display_name, message_sample, ai_score, ai_reason, status, group_id, created_at"
        ).in_("group_id", group_ids).order("ai_score", desc=True).execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
