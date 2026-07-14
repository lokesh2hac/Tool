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
# PROMPTS (all new – job posting focused)
# -------------------------------------------------------------------

KEYWORD_PROMPT = """You are a job market researcher. You need to generate search keywords to find Telegram GROUPS where people post **job openings** – especially work‑from‑home and monthly salary positions.

Brand/Topic: "{brand_name}" – but the groups may be general job boards, freelancing, remote work, etc.

Generate **at least 50 unique search keywords** (short: 1–4 words each) that can be used to discover such groups. Cover these categories:

1. **General job terms**:
   - "jobs", "hiring", "vacancy", "recruitment", "career", "opportunity"

2. **Work‑from‑home / remote**:
   - "work from home", "WFH", "remote jobs", "online work", "home based"

3. **Salary / pay**:
   - "salary", "monthly pay", "per month", "₹", "payroll"

4. **Job types**:
   - "part time", "full time", "freelance", "internship", "contract"

5. **Indian context**:
   - "India jobs", "Indian work", "desi jobs", "freshers", "experienced"

Rules:
- No duplicates.
- Mix English and Hinglish if helpful.
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


JOB_POSTING_ANALYSIS_PROMPT = """You are a job market researcher. We are scanning Telegram groups to find **legitimate job postings** – especially those offering **work‑from‑home** and **monthly salary** positions.

Analyze the given Telegram messages and identify posts that are **clearly hiring for a job or role**.

Strong signals (score high):
- "Work from home" / "WFH" / "Remote"
- "Salary: ₹X per month" / "Monthly pay" / "₹X/month"
- "Hiring" / "Recruitment" / "We are looking for"
- "Job opening" / "Vacancy" / "Position available"
- "Part‑time" / "Full‑time" / "Freelance"
- "Freshers welcome" / "Experience required"
- "Contact: @username" / "DM for details"
- "Salary: ₹15,000 – ₹25,000 per month"

Scoring guidelines (0-10):
- 9-10: Clear job posting with role, salary (preferably monthly), and contact/apply instructions.
- 7-8: Contains hiring language and some details, but missing salary or contact.
- 6: Mentions opportunities but not explicitly a job offer.

Mandatory:
- The message must be a **job offer / recruitment post** (not a general discussion or query).
- If ambiguous, skip.
- Deduplicate by message content (keep highest score).

Input format:
@username (Display Name): message text

Output: JSON array of job postings (max 15), sorted by score descending.
Each object:
{{
  "username": "@handle",
  "display_name": "Name",
  "score": 8,
  "reason": "why this is a strong job posting (mention WFH, salary, role, etc.)",
  "sample_message": "exact text of the job post",
  "is_indian_likely": true/false
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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
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
# AI CALLS
# -------------------------------------------------------------------
def _call_groq_sync(prompt: str, temperature: float = 0.2) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON. Escape all double quotes and newlines."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": 4096,
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(GROQ_URL, json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"})
        if resp.status_code != 200:
            raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text}")
        return resp.json()["choices"][0]["message"]["content"]


def _call_gemini_sync(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None, temperature: float = 0.2) -> str:
    api_key = _active_gemini_key or GEMINI_API_KEY
    model_name = (model or _active_gemini_model or DEFAULT_GEMINI_MODEL).strip()
    if not api_key:
        raise RuntimeError("No Gemini API key")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 4096},
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


async def _call_ai_async(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None, temperature: float = 0.2) -> str:
    async with _AI_SEMAPHORE:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(_call_ai_sync, prompt, key_id=key_id, model=model, temperature=temperature)
        )


def _call_ai_sync(prompt: str, key_id: Optional[str] = None, model: Optional[str] = None, temperature: float = 0.2) -> str:
    gemini_key = _active_gemini_key or GEMINI_API_KEY
    if gemini_key:
        try:
            return _call_gemini_sync(prompt, key_id=key_id, model=model, temperature=temperature)
        except GeminiRateLimitError:
            raise
        except Exception:
            pass
    return _call_groq_sync(prompt, temperature=temperature)


# -------------------------------------------------------------------
# PUBLIC FUNCTIONS – JOB POSTING ONLY
# -------------------------------------------------------------------

def _fallback_keywords(brand_name: str) -> List[str]:
    base = [
        "jobs", "hiring", "vacancy", "recruitment", "career",
        "work from home", "WFH", "remote jobs", "online work", "home based",
        "salary", "monthly pay", "per month", "payroll",
        "part time", "full time", "freelance", "internship", "contract",
        "India jobs", "freshers", "experienced", "job opening",
        "work from home jobs", "remote work india", "freelance india",
        "part time jobs", "full time jobs", "internship india",
        "fresher jobs", "experienced jobs", "salary per month",
        "work from home vacancy", "home based jobs", "online jobs india",
        "digital jobs", "content writing jobs", "data entry jobs",
        "customer service jobs", "teaching jobs", "tutor jobs",
        "admin jobs", "accounting jobs", "marketing jobs",
        "sales jobs", "it jobs", "software jobs", "web development jobs",
        "design jobs", "graphic design jobs", "video editing jobs",
        "social media jobs", "seo jobs", "digital marketing jobs",
        "hr jobs", "recruitment jobs", "bpo jobs", "call center jobs"
    ]
    unique = list(dict.fromkeys(base))
    while len(unique) < 50:
        unique.append(f"job{len(unique)}")
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
                    kw.append(f"job{len(kw)}")
                return kw[:50]
        return _fallback_keywords(brand_name)
    except GeminiRateLimitError:
        raise
    except Exception:
        return _fallback_keywords(brand_name)


async def analyze_job_postings(
    messages_list: List[Dict[str, Any]],
    brand_name: Optional[str] = None,
    key_id: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
    chunk_size: int = 30,
    delay_between_chunks: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Analyze messages to find job postings (recruitment ads).
    """
    if not messages_list:
        return []

    display_brand = brand_name if brand_name else "job listings"
    all_postings = []

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
        prompt = JOB_POSTING_ANALYSIS_PROMPT.format(brand_name=display_brand, messages=formatted)

        try:
            raw_text = await _call_ai_async(prompt, key_id=key_id, model=model)
            candidates = _extract_json(raw_text)
            if isinstance(candidates, list):
                filtered = [
                    c for c in candidates
                    if c.get("username") and c["username"].strip() not in ("@NoUsername", "@", "")
                ]
                all_postings.extend(filtered)
        except GeminiRateLimitError:
            raise
        except Exception as e:
            print(f"Job posting chunk {i//chunk_size + 1} failed: {e}")
            continue

        if i + chunk_size < len(messages_list):
            await asyncio.sleep(delay_between_chunks)

    # Deduplicate by message content – keep highest score
    unique = {}
    for c in all_postings:
        key = c.get("sample_message", "")[:100]
        if key not in unique or c.get("score", 0) > unique[key].get("score", 0):
            unique[key] = c

    final = list(unique.values())
    final.sort(key=lambda x: -int(x.get("score", 0)))
    return final[:15]


# ================================================================
# BACKWARD COMPATIBILITY – maps old 'analyze_candidates' to new job-posting analyzer
# ================================================================

async def analyze_candidates(
    messages_list: List[Dict[str, Any]],
    brand_name: Optional[str] = None,
    key_id: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
    chunk_size: int = 30,
    delay_between_chunks: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    This function is now an alias for analyze_job_postings().
    It finds job openings (WFH, monthly salary) instead of candidates.
    """
    return await analyze_job_postings(
        messages_list=messages_list,
        brand_name=brand_name,
        key_id=key_id,
        model=model,
        chunk_size=chunk_size,
        delay_between_chunks=delay_between_chunks,
    )