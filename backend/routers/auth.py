from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from lib.telegram_client import send_code, sign_in, active_clients
from lib.supabase_client import supabase

router = APIRouter()


class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str
    phone_code_hash: str  # sent back from frontend (returned by /send-code)


@router.post("/send-code")
async def api_send_code(body: SendCodeRequest, request: Request):
    """
    Step 1: Send OTP to phone number.
    Returns phone_code_hash to frontend — frontend must send it back in /verify-code.
    This avoids relying on cross-origin session cookies.
    """
    if not body.phone or len(body.phone) < 7:
        raise HTTPException(status_code=400, detail="Invalid phone number.")
    try:
        phone_code_hash = await send_code(body.phone)
        # Return hash to frontend — frontend stores it temporarily and sends back
        return {"success": True, "phone_code_hash": phone_code_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-code")
async def api_verify_code(body: VerifyCodeRequest, request: Request):
    """
    Step 2: Verify OTP using phone_code_hash returned from /send-code.
    Real Telegram verification — will fail with wrong phone or wrong OTP.
    """
    if not body.phone_code_hash:
        raise HTTPException(
            status_code=400,
            detail="phone_code_hash is required. Call /send-code first."
        )
    if not body.code or len(body.code) < 4:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    try:
        client, session_string, username = await sign_in(
            body.phone, body.code, body.phone_code_hash
        )
    except Exception as e:
        error_msg = str(e)
        # Give user-friendly error messages
        if "PHONE_CODE_INVALID" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid OTP code. Please try again.")
        elif "PHONE_CODE_EXPIRED" in error_msg:
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        elif "PHONE_NUMBER_INVALID" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid phone number.")
        elif "SESSION_PASSWORD_NEEDED" in error_msg:
            raise HTTPException(status_code=400, detail="Two-step verification is enabled on this account. Please disable it temporarily.")
        else:
            raise HTTPException(status_code=400, detail=f"Login failed: {error_msg}")

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

    # Set server-side session
    request.session["phone"] = body.phone
    return {"success": True, "username": username or body.phone}


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
