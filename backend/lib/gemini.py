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
# Correct model name: gemini-2.5-flash (official, no preview suffix)
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
)

CANDIDATE_ANALYSIS_PROMPT = """You are an expert talent scout for ACE2KING, a leading iGaming and sports betting platform targeting INDIA.
We need AFFILIATE MARKETING AGENTS and WEBSITE PROMOTER AGENTS who can bring Indian users to our platform.

Analyze the Telegram messages below. Identify users who are GENUINELY likely to be good affiliate/promoter candidates.

=== SCORING CRITERIA (1-10) ===

AFFILIATE/PROMOTER SIGNALS (most important):
- Runs Telegram channels, YouTube, Instagram, or websites
- Mentions SEO, paid ads, traffic, conversions, landing pages
- Talks about referral programs, commissions, earning online
- Experience in digital marketing, promoting apps or services
- Already promotes betting/fantasy/gaming apps (Dream11, MPL, etc.)
- Asks about affiliate links, payout methods, CPA/RevShare models

INDIA-FIT SIGNALS (high priority):
- Mentions India, Indian cities (Mumbai, Delhi, Bangalore, Hyderabad, Chennai, Kolkata, Pune, Jaipur, etc.)
- Uses Hinglish/Hindi: bhai, yaar, paise, kamai, paisa, rupee, lakh, crore
- References UPI, Paytm, PhonePe, GPay, INR, \u20b9
- Mentions IPL, cricket, kabaddi, Dream11, MPL, fantasy sports
- Indian telecom: Jio, Airtel, Vi
- Indian slang or regional language mixing

FALSE POSITIVE FILTERS (reduce score if):
- Just asking basic questions with no marketing context
- Spamming unrelated content
- Only talking about personal betting (player, not promoter)
- Bot-like repetitive messages

Messages (format: "@username (Display Name): message text"):
{messages}

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {{
    "username": "@handle_or_NoUsername",
    "display_name": "Full Name",
    "score": 8,
    "reason": "Runs a cricket tips Telegram channel, mentioned referral commissions, uses Hinglish",
    "sample_message": "exact quote from their message",
    "india_confidence": 0.9,
    "india_signals": ["Hinglish", "Mentioned IPL", "UPI reference"],
    "fit_tags": ["channel_owner", "affiliate_aware", "cricket_audience"],
    "is_indian_likely": true
  }}
]

Strict Rules:
- Only include users with score >= 6
- Deduplicate by username
- Maximum 20 candidates
- Prefer Indian users over non-Indian with same score
- Sort by score descending
- If no candidates qualify, return empty array []"""


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
            "temperature": 0.3,
            "maxOutputTokens": 8192,
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


async def generate_keywords(brand_name: str) -> list:
    """Generate iGaming Telegram search keywords for a brand."""
    prompt = (
        f"Generate exactly 5 Telegram search keywords for finding iGaming affiliate marketing groups "
        f"related to the brand or topic: '{brand_name}'. "
        f"Focus on Indian affiliate marketing, betting promotions, and iGaming communities. "
        f"Include India-specific keywords where relevant. "
        f"Return ONLY a valid JSON array of strings, no explanation, no markdown. "
        f'Example: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]'
    )
    try:
        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(None, _call_gemini_sync, prompt)
        raw = _strip_markdown(raw_text)
        keywords = json.loads(raw)
        if isinstance(keywords, list):
            return [str(k) for k in keywords[:5]]
        return [brand_name]
    except Exception:
        return [
            brand_name,
            f"{brand_name} affiliate india",
            f"{brand_name} promoter",
            "igaming affiliate india",
            "betting affiliate program india",
        ]


async def analyze_candidates(messages_list: list) -> list:
    """
    Analyze Telegram messages with smart Indian affiliate/promoter detection.
    Uses direct REST API - no SDK auth issues.
    """
    if not messages_list:
        return []

    formatted = "\n".join(
        f"@{m.get('sender_username', 'NoUsername')} ({m.get('sender_name', 'Unknown')}): {m.get('text', '')}"
        for m in messages_list
        if m.get("text")
    )

    if not formatted.strip():
        return []

    prompt = CANDIDATE_ANALYSIS_PROMPT.format(messages=formatted)

    try:
        loop = asyncio.get_event_loop()
        raw_text = await loop.run_in_executor(None, _call_gemini_sync, prompt)
        raw = _strip_markdown(raw_text)
        candidates = json.loads(raw)
        if isinstance(candidates, list):
            # Indian users first, then by score
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
