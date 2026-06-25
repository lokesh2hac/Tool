import os
import sys
import json
import re
import time
import random
import asyncio
import functools
import httpx
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    sys.exit("ERROR: GROQ_API_KEY is not set. Get free key from https://console.groq.com/keys")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

_active_gemini_key: str = ""
_active_gemini_model: str = DEFAULT_GEMINI_MODEL

# Global semaphore to limit concurrent AI requests across the whole app
# Set to 3 to allow a few parallel calls but not flood the API
_AI_SEMAPHORE = asyncio.Semaphore(3)


class GeminiRateLimitError(Exception):
    def __init__(self, key_id: Optional[str] = None):
        self.key_id = key_id or ""
        super().__init__(f"Gemini rate limit hit for key_id={key_id!r}")


class GeminiUnavailableError(Exception):
    pass


class GeminiParseError(Exception):
    pass


def _get_gemini_url(model: str = DEFAULT_GEMINI_MODEL) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def set_active_gemini_key(api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
    global _active_gemini_key, _active_gemini_model
    _active_gemini_key = api_key.strip() if api_key else ""
    _active_gemini_model = model.strip() if model else DEFAULT_GEMINI_MODEL


# -------------------------------------------------------------------
# PROMPTS (unchanged – kept short for brevity)
# -------------------------------------------------------------------
KEYWORD_PROMPT = """You are a Telegram group discovery expert for Indian iGaming affiliate recruitment.

Brand name: "{brand_name}"
Goal: Find public Telegram GROUPS (not channels) where affiliate agents and website promoters hang out. These agents recruit users for betting/gaming platforms and earn commissions.

Generate **at least 50 unique search keywords** (short: 1–4 words each) that can be used to discover such groups. Cover these 5 categories:

1. **Brand‑specific variations** (at least 10):
   - Exact brand, with "India", "official", "club", "community", "referral", "promo", "bonus", "agent", "affiliate", "partner".

2. **Affiliate / promoter terms** (at least 10):
   - "affiliate", "referral code", "commission", "earning", "income", "agent", "promoter", "recruitment", "team", "leader", "master agent", "sub agent".

3. **Category / gaming terms** (at least 10):
   - "betting", "cricket betting", "fantasy sports", "casino", "slot", "jackpot", "predictions", "tips", "odds", "exchange", "matka", "satta", "gaming app".

4. **Hinglish / Indian slang** (at least 10):
   - "paise kamao", "satta tips", "lagao", "jeet", "adda", "kamai online", "tipster", "betting ID", "UPI payment", "PhonePe", "GPay", "ipl betting".

5. **Action / recruitment phrases** (at least 10):
   - "join now", "earn with us", "refer and earn", "partner program", "work from home", "daily payout", "commission based", "recruiting agents", "become a promoter".

Rules:
- No duplicates.
- Mix English and Hinglish.
- Short (1–4 words).
- Focus on India.
- Return ONLY this JSON format:
{{
  "keywords": [
    "keyword1",
    "keyword2",
    ...
    "keyword50+"
  ]
}}
"""


CANDIDATE_ANALYSIS_PROMPT = """You are a talent scout for **{brand_name}** – a leading Indian gaming/betting platform. We are hiring **affiliate agents and website promoters** on a **commission‑based** model.

Analyze the given Telegram **group** messages and identify users actively promoting betting/gaming platforms.

Strong signals:
- Shares referral codes/links
- Direct recruitment language ("join me", "use my code", "earn with me", "commission")
- Mentions earning, UPI, Paytm, GPay
- Uses Hinglish, references IPL/cricket

Scoring (0-10):
- 9-10: Unambiguous promoter with referral link, active username, Indian
- 7-8: Strong promoter, recruitment language, audience likely
- 6: Promising but weaker evidence
Only score >= 6.

Mandatory: username must start with @ – otherwise skip.

Input format:
@username (Display Name): message text

Output: JSON array of candidates (max 15), sorted by score descending.
Each object:
{{
  "username": "@handle",
  "display_name": "Name",
  "score": 8,
  "reason": "short reason",
  "sample_message": "exact message (escape quotes and newlines)",
  "is_indian_likely": true/false,
  "existing_platform": "platform name if mentioned"
}}

Return only the JSON array.

Messages:
{messages}
"""


# -------------------------------------------------------------------
# JSON EXTRACTION
# -------------------------------------------------------------------
def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> Any:
    text = _strip_markdown(text)
    # Strategy 1: direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strategy 2: remove trailing commas
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Strategy 3: bracket balancing
    start = None
    for i, ch in enumerate(text):
        if ch in '{[':
            start = i
            break
    if start is None:
        raise ValueError("No JSON structure found")
    stack = []
    end = None
    for i in range(start, len(text)):
        ch = text[i]
        if ch in '{[':
            stack.append(ch)
        elif ch in '}]':
            if not stack:
                break
            opening = stack.pop()
            if (ch == '}' and opening != '{') or (ch == ']' and opening != '['):
                break
            if not stack:
                end = i + 1
                break
    if end is None:
        raise ValueError("Unbalanced JSON")
    candidate = text[start:end]
    candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}")


# -------------------------------------------------------------------
# AI CALLS with SEMAPHORE and RETRIES
# -------------------------------------------------------------------
def _call_groq_sync(prompt: str) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON. Escape all double quotes and newlines."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(GROQ_URL, json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"})
        if resp.status_code != 200:
            raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text}")
        return resp.json()["choices"][0]["message"]["content"]


def _call_gemini_sync(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None) -> str:
    api_key = _active_gemini_key or GEMINI_API_KEY
    model_name = (model or _active_gemini_model or DEFAULT_GEMINI_MODEL).strip()
    if not api_key:
        raise RuntimeError("No Gemini API key")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
        "systemInstruction": {"parts": [{"text": "Return ONLY valid JSON. Escape all double quotes and newlines."}]}
    }
    url = f"{_get_gemini_url(model_name)}?key={api_key}"
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if resp.status_code == 429:
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) + random.random() * 0.5
                        time.sleep(wait)
                        continue
                    else:
                        raise GeminiRateLimitError(key_id=key_id)
                if resp.status_code == 503:
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) + random.random() * 0.5
                        time.sleep(wait)
                        continue
                    else:
                        raise GeminiUnavailableError("Gemini unavailable after retries")
                if resp.status_code != 200:
                    raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text}")
                result = resp.json()
                candidates = result.get("candidates", [])
                if not candidates:
                    raise RuntimeError("No candidates in response")
                return candidates[0]["content"]["parts"][0]["text"]
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < max_retries - 1:
                wait = (2 ** attempt) + random.random() * 0.5
                time.sleep(wait)
                continue
            else:
                raise RuntimeError(f"Network error after retries: {e}")
    raise GeminiUnavailableError("Gemini unavailable")


async def _call_ai_async(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None) -> str:
    """
    Wrapper that uses a global semaphore to limit concurrency.
    """
    async with _AI_SEMAPHORE:
        loop = asyncio.get_event_loop()
        # Run the sync AI call in a thread pool
        return await loop.run_in_executor(
            None,
            functools.partial(_call_ai_sync, prompt, key_id=key_id, model=model)
        )


def _call_ai_sync(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None) -> str:
    """
    Try Gemini; on any error (except 429) fallback to Groq.
    """
    gemini_key = _active_gemini_key or GEMINI_API_KEY
    if gemini_key:
        try:
            return _call_gemini_sync(prompt, key_id=key_id, model=model)
        except GeminiRateLimitError:
            raise
        except Exception:
            pass
    return _call_groq_sync(prompt)


# -------------------------------------------------------------------
# PUBLIC FUNCTIONS
# -------------------------------------------------------------------
def _fallback_keywords(brand_name: str) -> List[str]:
    base = [
        brand_name, f"{brand_name} india", f"{brand_name} official", f"{brand_name} club",
        f"{brand_name} community", f"{brand_name} referral", f"{brand_name} promo",
        f"{brand_name} bonus", f"{brand_name} agent", f"{brand_name} affiliate",
        f"{brand_name} partner", f"{brand_name} earning", f"{brand_name} cricket",
        f"{brand_name} betting", "affiliate india", "betting affiliate", "igaming promoter",
        "referral code", "commission agent", "earn money online", "passive income",
        "work from home", "betting tips", "cricket betting", "fantasy sports",
        "satta matka", "matka tips", "online casino", "slot games", "jackpot",
        "predictions", "tipster", "betting exchange", "odds", "ipl betting",
        "dream11", "my11circle", "paytm first", "gpay betting", "phonepe betting",
        "upi payment", "paise kamao", "satta tips", "lagao", "jeet", "adda",
        "kamai online", "betting id", "join now", "refer and earn", "partner program",
        "recruiting agents", "become a promoter"
    ]
    unique = list(dict.fromkeys(base))
    while len(unique) < 50:
        unique.append(f"betting{len(unique)}")
    return unique[:50]


async def generate_keywords(brand_name: str, model: str = DEFAULT_GEMINI_MODEL) -> List[str]:
    prompt = KEYWORD_PROMPT.format(brand_name=brand_name)
    try:
        raw = await _call_ai_async(prompt, model=model)
        data = _extract_json(raw)
        if isinstance(data, dict) and "keywords" in data:
            kw = data["keywords"]
            if isinstance(kw, list) and len(kw) >= 20:
                while len(kw) < 50:
                    kw.append(f"{brand_name}search{len(kw)}")
                return kw[:50]
        return _fallback_keywords(brand_name)
    except GeminiRateLimitError:
        raise
    except Exception:
        return _fallback_keywords(brand_name)


async def analyze_candidates(
    messages_list: List[Dict[str, Any]],
    brand_name: Optional[str] = None,
    key_id: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
    chunk_size: int = 30,           # reduced from 50 to lower per-call load
    delay_between_chunks: float = 0.5,  # small pause between chunks
) -> List[Dict[str, Any]]:
    """
    Chunked analysis with rate control:
      - chunk_size: messages per AI call (default 30)
      - delay_between_chunks: seconds to wait after each chunk
    """
    if not messages_list:
        return []

    display_brand = brand_name if brand_name else "the gaming platform"
    all_candidates = []

    for i in range(0, len(messages_list), chunk_size):
        chunk = messages_list[i:i+chunk_size]

        formatted_lines = []
        for m in chunk:
            if not m.get("text"):
                continue
            username = m.get("sender_username", "").strip()
            sender = f"@{username}" if username else "@NoUsername"
            name = m.get("sender_name", "Unknown")
            msg = m["text"].replace('"', '\\"').replace('\n', '\\n')
            formatted_lines.append(f"{sender} ({name}): {msg}")

        if not formatted_lines:
            continue

        formatted = "\n".join(formatted_lines)
        prompt = CANDIDATE_ANALYSIS_PROMPT.format(brand_name=display_brand, messages=formatted)

        try:
            raw_text = await _call_ai_async(prompt, key_id=key_id, model=model)
            candidates = _extract_json(raw_text)
            if isinstance(candidates, list):
                filtered = [
                    c for c in candidates
                    if c.get("username") and c["username"].strip() not in ("@NoUsername", "@", "")
                ]
                all_candidates.extend(filtered)
        except GeminiRateLimitError:
            raise  # let caller handle
        except Exception as e:
            print(f"Chunk {i//chunk_size + 1} failed: {e}")
            continue

        # Pause between chunks to smooth out request rate
        if i + chunk_size < len(messages_list):
            await asyncio.sleep(delay_between_chunks)

    # Deduplicate and sort
    unique = {}
    for c in all_candidates:
        username = c.get("username", "").strip()
        if not username:
            continue
        if username not in unique or c.get("score", 0) > unique[username].get("score", 0):
            unique[username] = c

    final = list(unique.values())
    final.sort(
        key=lambda x: (
            0 if x.get("is_indian_likely") else 1,
            -int(x.get("score", 0))
        )
    )
    return final[:15]
