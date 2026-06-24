from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from lib.telegram_client import send_code, sign_in, active_clients, create_client, get_session_string
from lib.supabase_client import supabase

router = APIRouter()


class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


@router.post("/send-code")
async def api_send_code(body: SendCodeRequest, request: Request):
    try:
        phone_code_hash = await send_code(body.phone)
        request.session["phone_code_hash"] = phone_code_hash
        request.session["pending_phone"] = body.phone
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-code")
async def api_verify_code(body: VerifyCodeRequest, request: Request):
    phone_code_hash = request.session.get("phone_code_hash")
    if not phone_code_hash:
        raise HTTPException(status_code=400, detail="No pending OTP request. Please send code first.")

    try:
        client, session_string, username = await sign_in(
            body.phone, body.code, phone_code_hash
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save session to Supabase
    try:
        existing = supabase.table("telegram_sessions").select("id").eq("phone", body.phone).execute()
        if existing.data:
            supabase.table("telegram_sessions").update({
                "session_string": session_string,
                "username": username,
            }).eq("phone", body.phone).execute()
        else:
            supabase.table("telegram_sessions").insert({
                "phone": body.phone,
                "session_string": session_string,
                "username": username,
            }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")

    request.session["phone"] = body.phone
    request.session.pop("phone_code_hash", None)
    request.session.pop("pending_phone", None)

    return {"success": True, "username": username}


@router.get("/status")
async def api_status(request: Request):
    phone = request.session.get("phone")
    if not phone:
        return {"logged_in": False, "phone": None, "username": None}

    try:
        result = supabase.table("telegram_sessions").select("username").eq("phone", phone).execute()
        if result.data:
            username = result.data[0].get("username", "")
            return {"logged_in": True, "phone": phone, "username": username}
    except Exception:
        pass

    return {"logged_in": False, "phone": None, "username": None}


@router.post("/logout")
async def api_logout(request: Request):
    phone = request.session.get("phone")
    if phone and phone in active_clients:
        try:
            client = active_clients[phone]
            await client.disconnect()
            del active_clients[phone]
        except Exception:
            pass
    request.session.clear()
    return {"success": True}
