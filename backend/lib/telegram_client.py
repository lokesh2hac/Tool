import os
import sys
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Chat, Channel, InputMessagesFilterEmpty, PeerChannel
from telethon.errors import SessionPasswordNeededError

load_dotenv()

_API_ID_STR = os.getenv("TELEGRAM_API_ID", "")
_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

if not _API_ID_STR or not _API_HASH:
    sys.exit("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in your .env file.")

API_ID = int(_API_ID_STR)
API_HASH = _API_HASH

active_clients: dict = {}

def create_client(session_string: str = "") -> TelegramClient:
    return TelegramClient(StringSession(session_string), API_ID, API_HASH)

def get_session_string(client: TelegramClient) -> str:
    return client.session.save()

async def send_code(phone: str) -> str:
    client = create_client()
    await client.connect()
    active_clients[phone] = client
    result = await client.send_code_request(phone)
    return result.phone_code_hash

async def sign_in(phone: str, code: str, phone_code_hash: str):
    client = active_clients.get(phone)
    if client is None:
        client = create_client()
        await client.connect()
        active_clients[phone] = client
    await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    session_string = get_session_string(client)
    me = await client.get_me()
    return client, session_string, me.username or ""

async def sign_in_2fa(phone: str, password: str):
    client = active_clients.get(phone)
    if client is None:
        raise RuntimeError("No active session found. Please restart login.")
    await client.sign_in(password=password)
    session_string = get_session_string(client)
    me = await client.get_me()
    return client, session_string, me.username or ""

async def get_client_for_phone(phone: str, session_string: str) -> TelegramClient:
    if phone in active_clients:
        client = active_clients[phone]
        if client.is_connected():
            return client
    client = create_client(session_string)
    await client.connect()
    active_clients[phone] = client
    return client

# -------------------------------------------------------------------
# NEW: Improved search_groups – uses search_global + fallback
# -------------------------------------------------------------------
async def search_groups(client: TelegramClient, keyword: str, limit: int = 50) -> list:
    """
    Search PUBLIC Telegram groups using global search (messages) then fallback to SearchRequest.
    Returns list of groups with username, title, member_count.
    """
    groups = []
    seen = set()

    # Try search_global first (more effective for groups)
    try:
        result = await client.search_global(
            keyword,
            limit=limit * 2,  # get more messages to deduplicate
            filter=InputMessagesFilterEmpty()
        )
        for msg in result:
            if hasattr(msg, 'peer_id'):
                # Extract chat ID from peer
                chat_id = None
                if hasattr(msg.peer_id, 'channel_id'):
                    chat_id = msg.peer_id.channel_id
                elif hasattr(msg.peer_id, 'chat_id'):
                    chat_id = msg.peer_id.chat_id
                if not chat_id:
                    continue
                try:
                    entity = await client.get_entity(PeerChannel(chat_id))
                    if isinstance(entity, Channel):
                        # Skip broadcast channels
                        if getattr(entity, 'broadcast', False):
                            continue
                        username = getattr(entity, 'username', None)
                        if not username:
                            continue
                        title = getattr(entity, 'title', '')
                        member_count = getattr(entity, 'participants_count', 0) or 0
                        if chat_id not in seen:
                            seen.add(chat_id)
                            groups.append({
                                "group_title": title,
                                "group_username": username,
                                "member_count": member_count,
                                "description": "",
                            })
                except Exception:
                    continue
    except Exception as e:
        print(f"search_global failed: {e}, falling back to SearchRequest")

    # Fallback: if no groups found, use SearchRequest (less restrictive)
    if not groups:
        try:
            result2 = await client(SearchRequest(q=keyword, limit=limit))
            for chat in result2.chats:
                if isinstance(chat, Channel):
                    if getattr(chat, "broadcast", False):
                        continue
                    # We don't require megagroup anymore
                    username = getattr(chat, "username", "") or ""
                    if not username:
                        continue
                    title = getattr(chat, "title", "") or ""
                    if not title:
                        continue
                    member_count = getattr(chat, "participants_count", 0) or 0
                    if username not in seen:
                        seen.add(username)
                        groups.append({
                            "group_title": title,
                            "group_username": username,
                            "member_count": member_count,
                            "description": "",
                        })
                elif isinstance(chat, Chat):
                    username = getattr(chat, "username", "") or ""
                    if username:
                        title = getattr(chat, "title", "") or ""
                        groups.append({
                            "group_title": title,
                            "group_username": username,
                            "member_count": 0,
                            "description": "",
                        })
        except Exception as e:
            raise RuntimeError(f"Group search failed: {str(e)}")

    return groups

# -------------------------------------------------------------------
# Other functions remain unchanged
# -------------------------------------------------------------------

async def get_messages(client: TelegramClient, group_username: str, limit: int = 100) -> dict:
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

async def get_group_messages(client: TelegramClient, group_username: str, limit: int = 100) -> dict:
    return await get_messages(client, group_username, limit)

async def send_message(client: TelegramClient, username: str, message: str):
    try:
        await client.send_message(username, message)
    except Exception as e:
        raise RuntimeError(f"Failed to send message: {str(e)}")

async def can_send_messages(client: TelegramClient, group_username: str) -> bool:
    try:
        entity = await client.get_entity(group_username)
        if hasattr(entity, 'default_banned_rights') and entity.default_banned_rights:
            if entity.default_banned_rights.send_messages:
                return False
        return True
    except Exception:
        return False

async def send_message_to_group(client: TelegramClient, group_username: str, message: str):
    try:
        entity = await client.get_entity(group_username)
        await client.send_message(entity, message)
    except Exception as e:
        raise RuntimeError(f"Failed to send message to {group_username}: {str(e)}")

async def join_group(client: TelegramClient, group_username: str) -> bool:
    try:
        entity = await client.get_entity(group_username)
        await client.join_channel(entity)
        await asyncio.sleep(0.5)
        return True
    except Exception as e:
        if "You are already a member" in str(e):
            return True
        return False