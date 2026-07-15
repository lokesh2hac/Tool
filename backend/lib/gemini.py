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
# PROMPTS – TECH RECRUITER / CANDIDATE SEARCH
# -------------------------------------------------------------------

# NEW: group‑friendly keyword prompt – generates terms likely in group titles
KEYWORD_PROMPT = """You are a tech recruiter looking for public Telegram GROUPS where software developers gather.

We need to find groups where developers discuss programming, share knowledge, or look for jobs. Focus on groups where the **group name or description** likely contains these terms.

Generate **at least 50 search keywords** – each should be 1–4 words and likely to appear in a group title or username.

Cover these categories:

1. **General tech** (e.g., "programming", "coding", "dev", "tech")
2. **Language‑specific** ("C#", ".NET", "Python", "Node.js", "AI", "full stack", "backend", "frontend")
3. **Job / career** ("jobs", "hiring", "freelance", "remote work")
4. **Indian‑specific** ("India", "Bangalore", "Mumbai", "Indian developers")

Rules:
- Mix broad and specific keywords.
- Use exact phrases that might appear in group titles (e.g., "Python Developers" not just "Python").
- Avoid too generic words like "chat" or "group".
- Return ONLY this JSON format:
{{
  "keywords": [
    "Python Developers",
    "C# Programming",
    "Remote Jobs India",
    ...
  ]
}}
"""


CANDIDATE_ANALYSIS_PROMPT = """You are a tech recruiter. We are scanning Telegram groups to find **qualified developers** who are looking for remote work or have relevant experience.

We are hiring:
- Senior C# / .NET Developer
- Senior Python Developer
- AI Full-Stack Engineer
- Senior Node.js Developer

Requirements:
- 8+ years experience
- Bachelor's degree in CS or related
- Native-level English
- Scalable applications experience

Analyze the given messages and identify users who **are looking for jobs** or **have relevant skills**.

Strong signals:
- Mentions C#, .NET, Python, AI, Node.js, or similar.
- Says "looking for work", "open to work", "available for hire".
- Describes projects, experience, or stack.
- Has a GitHub or portfolio link.

Scoring (0-10):
- 9-10: Clearly states skills, experience, and availability.
- 7-8: Mentions skills and interest, but less detail.
- 6: Possibly relevant but weak evidence.

Mandatory:
- Username must start with @.
- Skip spam, bots, or irrelevant messages.

Input format:
@username (Display Name): message text

Output: JSON array of candidates (max 15), sorted by score descending.
Each object:
{{
  "username": "@handle",
  "display_name": "Name",
  "score": 8,
  "reason": "why this candidate is a good fit (skills, experience)",
  "sample_message": "exact text",
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
# FALLBACK KEYWORDS
# -------------------------------------------------------------------
def _fallback_keywords(brand_name: str) -> List[str]:
    base = [
        "Python Developers", "C# Programming", "Node.js Dev", "AI Engineering",
        "Full Stack Developers", "Backend Engineers", "Frontend Devs",
        "Remote Tech Jobs", "Freelance Programmers", "Indian Developers",
        "Software Jobs India", "Tech Community India", "Programmers Group",
        "Coding India", "Dev India", "Tech Jobs Bangalore", "Mumbai Developers",
        "Hyderabad Tech", "Pune Developers", "Noida Tech", "Gurgaon IT",
        "JavaScript Group", "React Developers", "Angular Group", "Django Developers",
        "Flask Python", "ASP.NET Core", "DevOps Engineers", "Cloud Developers",
        "Kubernetes Group", "Docker Community", "AI ML Group", "Data Science India",
        "Machine Learning Engineers", "Deep Learning", "Computer Vision",
        "NLP Group", "Blockchain Developers", "Web3 India", "Crypto Developers",
        "Rust Programming", "Go Developers", "Java Group", "Spring Boot",
        "Android Developers", "iOS Dev", "Flutter Group", "React Native",
        "Game Developers", "Unity Group", "Unreal Engine", "AR VR Developers"
    ]
    unique = list(dict.fromkeys(base))
    while len(unique) < 50:
        unique.append(f"tech{len(unique)}")
    return unique[:50]


# -------------------------------------------------------------------
# PUBLIC FUNCTIONS
# -------------------------------------------------------------------
async def generate_keywords(brand_name: str, model: str = DEFAULT_GEMINI_MODEL) -> List[str]:
    prompt = KEYWORD_PROMPT.format(brand_name=brand_name)
    try:
        raw = await _call_ai_async(prompt, model=model)
        data = _extract_json(raw)
        if isinstance(data, dict) and "keywords" in data:
            kw = data["keywords"]
            if isinstance(kw, list) and len(kw) >= 20:
                while len(kw) < 50:
                    kw.append(f"tech{len(kw)}")
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
    chunk_size: int = 30,
    delay_between_chunks: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Analyze messages to find qualified developer candidates.
    """
    if not messages_list:
        return []

    display_brand = brand_name if brand_name else "tech hiring"
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
            raise
        except Exception as e:
            print(f"Chunk {i//chunk_size + 1} failed: {e}")
            continue

        if i + chunk_size < len(messages_list):
            await asyncio.sleep(delay_between_chunks)

    unique = {}
    for c in all_candidates:
        key = c.get("username", "")
        if key not in unique or c.get("score", 0) > unique[key].get("score", 0):
            unique[key] = c

    final = list(unique.values())
    final.sort(key=lambda x: -int(x.get("score", 0)))
    return final[:15]