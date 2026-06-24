import os
import sys
import json
import re
import asyncio
import urllib.request
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    sys.exit("ERROR: GEMINI_API_KEY is not set. Get your key from https://aistudio.google.com/app/apikey")

# Direct REST API - no SDK, no OAuth issues
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
)

# ─────────────────────────────────────────
# KEYWORD GENERATION PROMPT
# ─────────────────────────────────────────
KEYWORD_PROMPT = """You are a Telegram group discovery expert for Indian iGaming affiliate recruitment.

Brand/Topic: '{brand_name}'

Generate FOUR SEPARATE search strategy arrays for Telegram group search.
Each strategy finds different types of relevant groups:

Strategy A - BRAND TERMS: Variations of the brand name itself (2 keywords)
Strategy B - AFFILIATE/PROMOTER TERMS: People who promote/earn from betting (3 keywords, India-focused)
Strategy C - CATEGORY TERMS: iGaming/betting community terms in English (3 keywords)
Strategy D - HINGLISH TERMS: Indian slang terms for earning/betting (2 keywords, use actual Hindi/Hinglish)

Rules:
- Each keyword should be 1-4 words max (short = better Telegram search results)
- NO duplicates across strategies
- Strategy D must use actual Hinglish like "paise kamao", "satta tips", "kamai online"

Return ONLY this exact JSON format, no markdown, no explanation:
{{
  "brand": ["kw1", "kw2"],
  "affiliate": ["kw1", "kw2", "kw3"],
  "category": ["kw1", "kw2", "kw3"],
  "hinglish": ["kw1", "kw2"]
}}"""


# ─────────────────────────────────────────
# CANDIDATE ANALYSIS PROMPT (token-efficient)
# ─────────────────────────────────────────
CANDIDATE_ANALYSIS_PROMPT = """Analyze these Telegram messages. Find users who could be AFFILIATE MARKETING AGENTS for an Indian iGaming/betting platform.

SHORTLIST if user:
- Has a Telegram username (starts with @) — REQUIRED for outreach
- Mentions: referrals, commissions, affiliate links, promoting apps, earning online
- Shows India signals: Hinglish, UPI/Paytm, cricket/IPL/Dream11, Indian cities
- Runs channels, websites, or has an audience

SKIP if user:
- Has no username (@NoUsername) — cannot be contacted
- Only asking questions, not a promoter
- Bot-like or spammy messages
- Only personal bettor, not a promoter

Messages:
{messages}

Return ONLY valid JSON array, no markdown:
[{{"username":"@handle","display_name":"Name","score":8,"reason":"brief reason","sample_message":"their exact message","is_indian_likely":true}}]

Rules: score>=6 only, deduplicate by username, max 15, sort by score desc, return [] if none qualify."""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _call_gemini_sync(prompt: str) -> str:
    """Direct REST call to Gemini API - no SDK, no OAuth."""
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Gemini HTTP {e.code}: {body}")


async def generate_keywords(brand_name: str) -> dict:
    """
    Generate multi-strategy search keywords.
    Returns dict: {brand, affiliate, category, hinglish}
    Falls back to hardcoded keywords if Gemini fails/rate-limited.
    """
    prompt = KEYWORD_PROMPT.format(brand_name=brand_name)
    try:
        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(None, _call_gemini_sync, prompt)
        raw = _strip_markdown(raw_text)
        keywords = json.loads(raw)
        if isinstance(keywords, dict):
            return keywords
        return _fallback_keywords(brand_name)
    except Exception:
        return _fallback_keywords(brand_name)


def _fallback_keywords(brand_name: str) -> dict:
    """Hardcoded fallback — works even when Gemini is rate-limited."""
    return {
        "brand": [brand_name, f"{brand_name} india"],
        "affiliate": [f"{brand_name} affiliate", "betting affiliate india", "igaming promoter india"],
        "category": ["cricket betting group", "fantasy sports india", "online earning india"],
        "hinglish": ["paise kamao online", "satta affiliate"],
    }


async def analyze_candidates(messages_list: list) -> list:
    """
    Analyze messages to find shortlistable affiliate candidates.
    Only includes users WITH a Telegram username (outreach-ready).
    Token-efficient prompt to avoid rate limits.
    """
    if not messages_list:
        return []

    # Only include messages from users who HAVE a username — no username = can't contact
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

    # Truncate to 150 messages max to save tokens
    formatted = "\n".join(formatted_lines[:150])
    prompt = CANDIDATE_ANALYSIS_PROMPT.format(messages=formatted)

    try:
        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(None, _call_gemini_sync, prompt)
        raw = _strip_markdown(raw_text)
        candidates = json.loads(raw)
        if isinstance(candidates, list):
            # Filter: must have real username, not @NoUsername
            candidates = [
                c for c in candidates
                if c.get("username") and c["username"] != "@NoUsername"
            ]
            # Sort: Indian first, then by score
            candidates.sort(
                key=lambda x: (
                    0 if x.get("is_indian_likely") else 1,
                    -int(x.get("score", 0))
                )
            )
            return candidates
        return []
    except Exception as e:
        raise RuntimeError(f"Gemini analysis failed: {str(e)}")
