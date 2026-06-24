import os
import sys
import json
import re
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    sys.exit("ERROR: GROQ_API_KEY is not set. Get free key from https://console.groq.com/keys")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


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
# CANDIDATE ANALYSIS PROMPT
# ─────────────────────────────────────────
CANDIDATE_ANALYSIS_PROMPT = """Analyze these Telegram messages. Find users who could be AFFILIATE MARKETING AGENTS for an Indian iGaming/betting platform.

An **affiliate agent** is someone actively recruiting others to sign up / deposit / play through their personal referral code, link, or channel.
Examples of strong signals:
- Shares a referral code/link (e.g., "Use my code", "Sign up here", "Referral bonus", specific platform codes like 1xBet, Betway, Dafabet, Parimatch)
- Invites people to DM/join for earning, commissions, or tips
- Posts about "earning online", "passive income", "make money" tied to betting apps
- Has a channel/group link and says "join for tips", "free predictions", "daily earning"
- Promotes direct download APK links with earning claims

India-specific signals (raise confidence):
- Uses Hinglish words: paisa, kamai, satta, adda, tip, betting ID, lagao
- Mentions UPI apps: Paytm, PhonePe, Google Pay, GPay
- References cricket, IPL, Dream11, fantasy, Indian city names

Scoring guidelines (0-10):
- 9-10: Unambiguous affiliate - shares own referral code/link, asks people to DM, has username, clearly Indian
- 7-8: Strong promoter - mentions earning by invitation, has audience, but link/code not visible in sample
- 6: Likely promoter - uses language like "earn money", "join me", but evidence is thin
(Only output score >= 6)

Mandatory requirements:
- The user MUST have a Telegram username (starts with @) - otherwise skip entirely
- Skip bots, spam accounts, users who only ask questions, personal bettors who don't recruit
- If a user has multiple messages, pick the one that best demonstrates their score

Input format:
Each line is: @username (Display Name): message text

Return ONLY this exact JSON array - no markdown, no explanation:
[
  {{
    "username": "@handle",
    "display_name": "Name",
    "score": 8,
    "reason": "short reason why this person is an affiliate",
    "sample_message": "exact message text that proves it",
    "is_indian_likely": true
  }}
]

Rules:
- score >= 6 only
- deduplicate by username (keep the highest score)
- maximum 15 results, sorted by score descending (then Indian-first)
- return empty array [] if none qualify
- output only the JSON array, nothing else

Messages:
{messages}"""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ─────────────────────────────────────────
# GROQ CALL (httpx - works with Cloudflare)
# ─────────────────────────────────────────
def _call_groq_sync(prompt: str) -> str:
    """REST call to Groq using httpx — bypasses Cloudflare block that urllib gets."""
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


# ─────────────────────────────────────────
# PUBLIC FUNCTIONS
# ─────────────────────────────────────────
async def generate_keywords(brand_name: str) -> dict:
    """
    Generate multi-strategy search keywords using Groq.
    Returns dict: {brand, affiliate, category, hinglish}
    Falls back to hardcoded keywords if Groq fails.
    """
    prompt = KEYWORD_PROMPT.format(brand_name=brand_name)
    try:
        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(None, _call_groq_sync, prompt)
        raw = _strip_markdown(raw_text)
        keywords = json.loads(raw)
        if isinstance(keywords, dict):
            return keywords
        return _fallback_keywords(brand_name)
    except Exception:
        return _fallback_keywords(brand_name)


def _fallback_keywords(brand_name: str) -> dict:
    """Hardcoded fallback — works even when Groq is down."""
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
    Uses Groq llama-3.3-70b-versatile.
    """
    if not messages_list:
        return []

    # Format messages — tag @NoUsername so AI knows to skip them
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
        raw_text = await loop.run_in_executor(None, _call_groq_sync, prompt)
        raw = _strip_markdown(raw_text)
        candidates = json.loads(raw)
        if isinstance(candidates, list):
            # Hard filter: must have real username — no username = can't do outreach
            candidates = [
                c for c in candidates
                if c.get("username") and c["username"].strip() not in ("@NoUsername", "@", "")
            ]
            # Sort: Indian first, then by score desc
            candidates.sort(
                key=lambda x: (
                    0 if x.get("is_indian_likely") else 1,
                    -int(x.get("score", 0))
                )
            )
            return candidates
        return []
    except Exception as e:
        raise RuntimeError(f"AI analysis failed: {str(e)}")
