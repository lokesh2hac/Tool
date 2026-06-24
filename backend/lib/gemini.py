import os
import sys
import json
import re
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


class GeminiRateLimitError(Exception):
    def __init__(self, key_id: Optional[str] = None):
        self.key_id = key_id or ""
        super().__init__(f"Gemini rate limit hit for key_id={key_id!r}")


def _get_gemini_url(model: str = DEFAULT_GEMINI_MODEL) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def set_active_gemini_key(api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
    global _active_gemini_key, _active_gemini_model
    _active_gemini_key = api_key.strip() if api_key else ""
    _active_gemini_model = model.strip() if model else DEFAULT_GEMINI_MODEL


# -------------------------------------------------------------------
# PROMPTS
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
- No duplicates across categories.
- Mix English and Hinglish.
- All keywords must be short (1–4 words) for effective Telegram search.
- Focus heavily on India (Indian users, Indian payment methods, cricket/ipl context).
- The keywords should be optimised for finding GROUPS (i.e., they will be used in Telegram search for groups).

Return ONLY this exact JSON format – no markdown, no explanation:
{{
  "keywords": [
    "keyword1",
    "keyword2",
    ...
    "keyword50+"
  ]
}}

The list must contain at least 50 unique keywords.
"""


CANDIDATE_ANALYSIS_PROMPT = """You are a talent scout for **{brand_name}** – a leading Indian gaming/betting platform. We are hiring **affiliate agents and website promoters** on a **commission‑based** model.

Your task: Analyze the given Telegram **group** messages and **identify users who are actively promoting betting/gaming platforms** and could be recruited as our agents.

---

**What we are looking for** (strong signals, score high):

1. **Referral links/codes** – They share their own referral code/link for any betting site (e.g., 1xBet, Betway, Parimatch, Dafabet, etc.). This proves they already know how to recruit.
2. **Direct recruitment language** – "Join me", "Use my code", "Earn with me", "Become a sub‑agent", "Commission for every player", "Free tips with my link".
3. **Monetization** – They mention earning money, passive income, daily payouts, UPI payments (Paytm, GPay, PhonePe).
4. **Audience building** – They run a channel/group, give predictions, betting tips, and ask people to DM or join.
5. **Indian context** – They use Hinglish, reference IPL, cricket, Indian cities, and Indian payment methods.

**Scoring guidelines (0–10)** – only consider users with score ≥ 6:

- **9‑10**: Unambiguous promoter – shares own referral code/link, encourages sign‑ups, has an active Telegram username (@handle), clearly Indian, and shows evidence of existing recruitment.
- **7‑8**: Strong promoter – uses recruitment language, has a channel/group, but referral link not visible in the sample; likely has an audience.
- **6**: Promising – mentions earning, joining, or tips, but evidence is weaker.

**Mandatory filters (automatic rejection)**:
- No Telegram username (starts with @) → skip (we need to DM them).
- Bots, spam accounts, or users who only ask questions → skip.
- Personal bettors who do not recruit → skip.

**Input format** (each line):
@username (Display Name): message text

**Output**: Return ONLY a JSON array of candidate objects, sorted by **score descending**, with a maximum of **15 results**. Each object:

{{
  "username": "@handle",
  "display_name": "Name",
  "score": 8,
  "reason": "Concise reason why this person is a strong affiliate/promoter (mention referral code, recruitment language, etc.)",
  "sample_message": "The exact message text that proves it",
  "is_indian_likely": true/false,
  "existing_platform": "If they mention a specific platform (e.g., 1xBet, Betway) – useful for competitive recruitment"
}}

**Extra requirements**:
- Deduplicate by username – keep highest score.
- Indian candidates should be prioritised (sort: Indian‑first, then score high‑to‑low).
- If none qualify, return empty array [].

**Here are the messages**:
{messages}
"""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# -------------------------------------------------------------------
# AI CALLS (httpx based)
# -------------------------------------------------------------------
def _call_groq_sync(prompt: str) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert AI assistant. Always return valid JSON exactly as instructed. No markdown, no explanation, no extra text."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
        "stream": False,
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            GROQ_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text}")
        result = resp.json()
    return result["choices"][0]["message"]["content"]


def _call_gemini_sync(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None) -> str:
    api_key = _active_gemini_key or GEMINI_API_KEY
    model_name = (model or _active_gemini_model or DEFAULT_GEMINI_MODEL).strip()
    if not api_key:
        raise RuntimeError("No Gemini API key configured")

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
        "systemInstruction": {
            "parts": [{"text": "You are an expert AI assistant. Always return valid JSON exactly as instructed. No markdown, no explanation, no extra text."}]
        }
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{_get_gemini_url(model_name)}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 429:
            raise GeminiRateLimitError(key_id=key_id)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text}")
        result = resp.json()

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates in response")
    return candidates[0]["content"]["parts"][0]["text"]


def _call_ai_sync(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None) -> str:
    gemini_key = _active_gemini_key or GEMINI_API_KEY
    if gemini_key:
        return _call_gemini_sync(prompt, key_id=key_id, model=model)
    return _call_groq_sync(prompt)


# -------------------------------------------------------------------
# PUBLIC FUNCTIONS
# -------------------------------------------------------------------
def _fallback_keywords(brand_name: str) -> List[str]:
    """Return at least 50 fallback keywords."""
    base = [
        brand_name,
        f"{brand_name} india",
        f"{brand_name} official",
        f"{brand_name} club",
        f"{brand_name} community",
        f"{brand_name} referral",
        f"{brand_name} promo",
        f"{brand_name} bonus",
        f"{brand_name} agent",
        f"{brand_name} affiliate",
        f"{brand_name} partner",
        f"{brand_name} earning",
        f"{brand_name} cricket",
        f"{brand_name} betting",
        "affiliate india",
        "betting affiliate",
        "igaming promoter",
        "referral code",
        "commission agent",
        "earn money online",
        "passive income",
        "work from home",
        "betting tips",
        "cricket betting",
        "fantasy sports",
        "satta matka",
        "matka tips",
        "online casino",
        "slot games",
        "jackpot",
        "predictions",
        "tipster",
        "betting exchange",
        "odds",
        "ipl betting",
        "dream11",
        "my11circle",
        "paytm first",
        "gpay betting",
        "phonepe betting",
        "upi payment",
        "paise kamao",
        "satta tips",
        "lagao",
        "jeet",
        "adda",
        "kamai online",
        "betting id",
        "join now",
        "refer and earn",
        "partner program",
        "recruiting agents",
        "become a promoter"
    ]
    unique = list(dict.fromkeys(base))
    while len(unique) < 50:
        unique.append(f"betting{len(unique)}")
    return unique[:50]


async def generate_keywords(brand_name: str, model: str = DEFAULT_GEMINI_MODEL) -> List[str]:
    """
    Generate at least 50 search keywords as a flat list.
    Falls back to hardcoded list if AI fails.
    """
    prompt = KEYWORD_PROMPT.format(brand_name=brand_name)
    try:
        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(
            None,
            functools.partial(_call_ai_sync, prompt, model=model),
        )
        raw = _strip_markdown(raw_text)
        data = json.loads(raw)
        if isinstance(data, dict) and "keywords" in data:
            keywords = data["keywords"]
            if isinstance(keywords, list) and len(keywords) >= 20:
                while len(keywords) < 50:
                    keywords.append(f"{brand_name}search{len(keywords)}")
                return keywords[:50]
        return _fallback_keywords(brand_name)
    except GeminiRateLimitError:
        raise
    except Exception:
        return _fallback_keywords(brand_name)


async def analyze_candidates(
    messages_list: List[Dict[str, Any]],
    brand_name: Optional[str] = None,        # now optional; uses placeholder if None
    key_id: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL
) -> List[Dict[str, Any]]:
    """
    Analyze messages to find shortlistable affiliate candidates.
    Only includes users WITH a Telegram username (outreach-ready).
    Raises GeminiRateLimitError if rate limited.
    """
    if not messages_list:
        return []

    display_brand = brand_name if brand_name else "the gaming platform"

    formatted_lines = []
    for m in messages_list:
        if not m.get("text"):
            continue
        username = m.get("sender_username", "").strip()
        sender = f"@{username}" if username else "@NoUsername"
        name = m.get("sender_name", "Unknown")
        formatted_lines.append(f"{sender} ({name}): {m['text']}")

    if not formatted_lines:
        return []

    formatted = "\n".join(formatted_lines[:150])
    prompt = CANDIDATE_ANALYSIS_PROMPT.format(brand_name=display_brand, messages=formatted)

    loop = asyncio.get_event_loop()
    try:
        raw_text = await loop.run_in_executor(
            None,
            functools.partial(_call_ai_sync, prompt, key_id=key_id, model=model),
        )
        raw = _strip_markdown(raw_text)
        candidates = json.loads(raw)
    except GeminiRateLimitError:
        raise
    except Exception as e:
        raise RuntimeError(f"AI analysis failed: {str(e)}")

    if isinstance(candidates, list):
        candidates = [
            c for c in candidates
            if c.get("username") and c["username"].strip() not in ("@NoUsername", "@", "")
        ]
        candidates.sort(
            key=lambda x: (
                0 if x.get("is_indian_likely") else 1,
                -int(x.get("score", 0))
            )
        )
        return candidates
    return []
