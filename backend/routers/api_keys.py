from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from lib.supabase_client import supabase

router = APIRouter()


def _require_session(request: Request):
    phone = request.session.get("phone")
    if not phone:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return phone


def _mask_key(api_key: str) -> str:
    """Show only last 6 chars of the API key."""
    if len(api_key) <= 6:
        return "****" + api_key
    return "****" + api_key[-6:]


class AddApiKeyRequest(BaseModel):
    label: str
    provider: str = "gemini"
    api_key: str


@router.get("")
async def list_api_keys(request: Request):
    """List all API keys (masked)."""
    _require_session(request)
    try:
        res = supabase.table("api_keys").select(
            "id, label, provider, api_key, is_active, rate_limited_until, created_at"
        ).order("created_at", desc=False).execute()
        keys = res.data or []
        # Mask the key value
        for key in keys:
            key["masked_key"] = _mask_key(key["api_key"])
            del key["api_key"]
        return keys
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def add_api_key(body: AddApiKeyRequest, request: Request):
    """Add a new API key."""
    _require_session(request)
    if not body.label.strip():
        raise HTTPException(status_code=400, detail="Label is required")
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")
    try:
        res = supabase.table("api_keys").insert({
            "label": body.label.strip(),
            "provider": body.provider.strip() or "gemini",
            "api_key": body.api_key.strip(),
            "is_active": True,
        }).execute()
        row = res.data[0]
        row["masked_key"] = _mask_key(row["api_key"])
        del row["api_key"]
        return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key_id}")
async def delete_api_key(key_id: str, request: Request):
    """Delete an API key."""
    _require_session(request)
    try:
        supabase.table("api_keys").delete().eq("id", key_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{key_id}/mark-rate-limited")
async def mark_rate_limited(key_id: str, request: Request):
    """Mark a key as rate limited for 1 hour."""
    _require_session(request)
    try:
        rate_limited_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        supabase.table("api_keys").update({
            "rate_limited_until": rate_limited_until,
        }).eq("id", key_id).execute()
        return {"success": True, "rate_limited_until": rate_limited_until}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{key_id}/clear-rate-limit")
async def clear_rate_limit(key_id: str, request: Request):
    """Clear rate limit on a key."""
    _require_session(request)
    try:
        supabase.table("api_keys").update({
            "rate_limited_until": None,
        }).eq("id", key_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
