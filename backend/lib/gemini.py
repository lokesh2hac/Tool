import os
import sys
import json
import re
import asyncio
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    sys.exit("ERROR: GEMINI_API_KEY is not set.")

genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-2.5-flash-preview-05-20"

CANDIDATE_ANALYSIS_PROMPT = """You are an HR assistant for ACE2KING, a leading iGaming and sports betting platform.
We are recruiting AFFILIATE MARKETING AGENTS and WEBSITE PROMOTER AGENTS on a commission basis.

Analyze the following Telegram group messages and identify potential candidates.

Score each unique user from 1 to 10 based on:
- Experience in affiliate marketing, betting promotion, or iGaming
- Mentions of traffic generation, websites, SEO, referrals, or commissions
- Interest in earning money online or side income
- Promoter/marketer language and behavior
- Social media presence or influencer signals

Messages (format: "Username: message text"):
{messages}

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {{
    "username": "@handle_or_NoUsername",
    "display_name": "Full Name",
    "score": 8,
    "reason": "Mentioned running affiliate websites and experience with betting promotions",
    "sample_message": "exact quote from their message"
  }}
]

Rules:
- Only include users with score >= 6
- Deduplicate by username
- Maximum 20 candidates
- If no candidates qualify, return empty array []"""


def _strip_markdown(text: str) -> str:
    """Remove markdown code fences from Gemini response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _call_gemini_sync(prompt: str) -> str:
    """Run a synchronous Gemini API call."""
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text


async def generate_keywords(brand_name: str) -> list:
    """Ask Gemini 2.5 Flash to generate 5 iGaming search keywords."""
    prompt = (
        f"Generate exactly 5 Telegram search keywords for finding iGaming affiliate marketing groups "
        f"related to the brand or topic: '{brand_name}'. "
        f"Focus on affiliate marketing, betting promotions, and iGaming communities. "
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
            f"{brand_name} affiliate",
            f"{brand_name} promoter",
            "igaming affiliate",
            "betting affiliate program",
        ]


async def analyze_candidates(messages_list: list) -> list:
    """Analyze Telegram messages with Gemini 2.5 Flash to find affiliate candidates."""
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
            return candidates
        return []
    except Exception as e:
        raise RuntimeError(f"Gemini analysis failed: {str(e)}")
