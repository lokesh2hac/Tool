from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from telethon.errors import SessionPasswordNeededError
from lib.telegram_client import send_code, sign_in, sign_in_2fa, active_clients
from lib.supabase_client import supabase

router = APIRouter()


class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str
    phone_code_hash: str


class VerifyPasswordRequest(BaseModel):
    phone: str
    password: str


async def _save_session(phone: str, session_string: str, username: str, app_user_phone: str):
    """
    Upsert telegram session to Supabase.
    Now includes app_user_phone so we can link sessions to the logged‑in user.
    """
    existing = supabase.table("telegram_sessions").select("id").eq("phone", phone).execute()
    if existing.data:
        supabase.table("telegram_sessions").update({
            "session_string": session_string,
            "username": username,
            "app_user_phone": app_user_phone,  # 👈 ensure it's set
        }).eq("phone", phone).execute()
    else:
        supabase.table("telegram_sessions").insert({
            "phone": phone,
            "session_string": session_string,
            "username": username,
            "app_user_phone": app_user_phone,  # 👈 new field
        }).execute()


@router.post("/send-code")
async def api_send_code(body: SendCodeRequest, request: Request):
    """
    Step 1: Send OTP to phone number.
    Returns phone_code_hash to frontend.
    """
    if not body.phone or len(body.phone) < 7:
        raise HTTPException(status_code=400, detail="Invalid phone number.")
    try:
        phone_code_hash = await send_code(body.phone)
        return {"success": True, "phone_code_hash": phone_code_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-code")
async def api_verify_code(body: VerifyCodeRequest, request: Request):
    """
    Step 2: Verify OTP.
    If 2FA is enabled, returns {requires_password: true} instead of logging in.
    """
    if not body.phone_code_hash:
        raise HTTPException(status_code=400, detail="phone_code_hash is required. Call /send-code first.")
    if not body.code or len(body.code) < 4:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    try:
        client, session_string, username = await sign_in(
            body.phone, body.code, body.phone_code_hash
        )
    except SessionPasswordNeededError:
        # 2FA is enabled — tell frontend to ask for password
        return {"success": True, "requires_password": True, "phone": body.phone}
    except Exception as e:
        error_msg = str(e)
        if "PHONE_CODE_INVALID" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid OTP code. Please try again.")
        elif "PHONE_CODE_EXPIRED" in error_msg:
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        elif "PHONE_NUMBER_INVALID" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid phone number.")
        else:
            raise HTTPException(status_code=400, detail=f"Login failed: {error_msg}")

    # Get the app user's phone from the session (it's the same as body.phone for first login)
    app_user_phone = body.phone  # after login, we store this in session
    try:
        await _save_session(body.phone, session_string, username, app_user_phone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")

    request.session["phone"] = body.phone
    # Also set the active Telegram phone to this one by default
    request.session["active_telegram_phone"] = body.phone
    return {"success": True, "requires_password": False, "username": username or body.phone}


@router.post("/verify-password")
async def api_verify_password(body: VerifyPasswordRequest, request: Request):
    """
    Step 3 (only if 2FA enabled): Submit cloud password to complete login.
    """
    if not body.phone or not body.password:
        raise HTTPException(status_code=400, detail="Phone and password are required.")

    try:
        client, session_string, username = await sign_in_2fa(body.phone, body.password)
    except Exception as e:
        error_msg = str(e)
        if "PASSWORD_HASH_INVALID" in error_msg or "is invalid" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Incorrect 2FA password. Please try again.")
        else:
            raise HTTPException(status_code=400, detail=f"2FA login failed: {error_msg}")

    app_user_phone = body.phone
    try:
        await _save_session(body.phone, session_string, username, app_user_phone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")

    request.session["phone"] = body.phone
    request.session["active_telegram_phone"] = body.phone
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
