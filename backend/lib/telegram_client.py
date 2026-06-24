import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest

load_dotenv()

_API_ID_STR = os.getenv("TELEGRAM_API_ID", "")
_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

if not _API_ID_STR or not _API_HASH:
    sys.exit("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in your .env file.")

API_ID = int(_API_ID_STR)
API_HASH = _API_HASH

# In-memory store of active clients keyed by phone
active_clients: dict = {}


def create_client(session_string: str = "") -> TelegramClient:
    """Create a TelegramClient with optional existing StringSession."""
    return TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH,
    )


def get_session_string(client: TelegramClient) -> str:
    """Extract the StringSession string from a connected client."""
    return client.session.save()


async def send_code(phone: str) -> str:
    """Send OTP to the given phone number. Returns phone_code_hash."""
    client = create_client()
    await client.connect()
    active_clients[phone] = client
    result = await client.send_code_request(phone)
    return result.phone_code_hash


async def sign_in(phone: str, code: str, phone_code_hash: str):
    """
    Sign in with OTP. Returns (client, session_string, username).
    """
    client = active_clients.get(phone)
    if client is None:
        client = create_client()
        await client.connect()
        active_clients[phone] = client

    await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    session_string = get_session_string(client)
    me = await client.get_me()
    username = me.username or ""
    return client, session_string, username


async def get_client_for_phone(phone: str, session_string: str) -> TelegramClient:
    """Return active client or reconnect from saved session_string."""
    if phone in active_clients:
        client = active_clients[phone]
        if client.is_connected():
            return client
    client = create_client(session_string)
    await client.connect()
    active_clients[phone] = client
    return client


async def search_groups(client: TelegramClient, keyword: str, limit: int = 20) -> list:
    """Search for Telegram groups by keyword. Returns list of group dicts."""
    try:
        result = await client(SearchRequest(q=keyword, limit=limit))
        groups = []
        for chat in result.chats:
            chat_dict = {
                "group_title": getattr(chat, "title", ""),
                "group_username": getattr(chat, "username", "") or "",
                "member_count": getattr(chat, "participants_count", 0) or 0,
                "description": "",
            }
            if chat_dict["group_title"]:
                groups.append(chat_dict)
        return groups
    except Exception as e:
        raise RuntimeError(f"Group search failed: {str(e)}")


async def get_messages(client: TelegramClient, group_username: str, limit: int = 100) -> dict:
    """Fetch last `limit` messages from a group. Returns dict with messages list and group_title."""
    try:
        entity = await client.get_entity(group_username)
        group_title = getattr(entity, "title", group_username)
        messages = await client.get_messages(entity, limit=limit)
        result = []
        for msg in messages:
            if not msg.text:
                continue
            sender_name = ""
            sender_username = ""
            if msg.sender:
                sender_name = " ".join(
                    filter(None, [
                        getattr(msg.sender, "first_name", "") or "",
                        getattr(msg.sender, "last_name", "") or "",
                    ])
                ).strip() or "Unknown"
                sender_username = getattr(msg.sender, "username", "") or ""
            result.append({
                "id": msg.id,
                "text": msg.text,
                "sender_name": sender_name,
                "sender_username": sender_username,
                "date": msg.date.isoformat() if msg.date else "",
            })
        return {"messages": result, "group_title": group_title}
    except Exception as e:
        raise RuntimeError(f"Failed to fetch messages: {str(e)}")


async def send_message(client: TelegramClient, username: str, message: str):
    """Send a direct message to a Telegram user."""
    try:
        await client.send_message(username, message)
    except Exception as e:
        raise RuntimeError(f"Failed to send message: {str(e)}")
