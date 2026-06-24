# ACE2KING — Telegram Affiliate Candidate Finder

A full-stack HR tool for finding and recruiting affiliate marketing agents and website promoters from Telegram public groups, powered by AI with Gemini and Groq support.

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                  WEB APPLICATION (React + Vite)            │
│  ┌──────────┐   ┌─────────────────┐   ┌────────────────┐  │
│  │  Login   │   │  Dashboard      │   │  Outreach      │  │
│  │  (OTP)   │   │  Group Search   │   │  History       │  │
│  └──────────┘   └─────────────────┘   └────────────────┘  │
└────────────────────────┬──────────────────────────────────┘
                         │ HTTP /api/*
         ┌───────────────┼──────────────────┐
         ▼               ▼                  ▼
   Telegram API   Gemini/Groq AI      Supabase DB
   (Telethon       (Keyword           (Sessions,
   MTProto)        Expansion &        Candidates,
                   Candidate          Outreach Logs)
                   Scoring)
```

**Backend:** FastAPI (Python) · **Frontend:** React + Vite + TailwindCSS
**AI:** Gemini 2.5 Flash / Gemini 1.5 Flash / Groq llama-3.3-70b · **Telegram:** Telethon MTProto StringSession
**Database:** Supabase (PostgreSQL)

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- A [Supabase](https://supabase.com) project
- [Telegram API credentials](https://my.telegram.org)
- [Google Gemini API key](https://aistudio.google.com/app/apikey)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/lokesh2hac/Tool.git
cd Tool
```

### 2. Supabase Database Setup

1. Go to your [Supabase dashboard](https://app.supabase.com) and open your project.
2. Navigate to **SQL Editor** and run the contents of `supabase/schema.sql`.
3. This creates four tables: `telegram_sessions`, `scanned_groups`, `candidates`, `outreach_logs`.

### 3. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and fill in your API keys (see below)

# Start the backend server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

> **Note:** Vite is configured to proxy all `/api` requests to `http://localhost:8000`, so no CORS issues during development.

---

## Environment Variables (`backend/.env`)

| Variable | Description | Where to Get |
|---|---|---|
| `TELEGRAM_API_ID` | Telegram app API ID | [my.telegram.org](https://my.telegram.org) |
| `TELEGRAM_API_HASH` | Telegram app API Hash | [my.telegram.org](https://my.telegram.org) |
| `GEMINI_API_KEY` | Google Gemini API key | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `SUPABASE_URL` | Supabase project URL | Supabase → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | Supabase → Project Settings → API |
| `SECRET_KEY` | Random string for session encryption | Any random secret (e.g. `openssl rand -hex 32`) |

---

## Getting API Keys

### Telegram API ID & Hash

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click **"API development tools"**
4. Create a new application
5. Copy `api_id` and `api_hash`

### Google Gemini API Key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **"Create API key"**
3. Copy the key

### Supabase Project

1. Go to [https://supabase.com](https://supabase.com) and create a new project
2. Go to **Project Settings → API**
3. Copy the **Project URL** and **anon public** key
4. Run `supabase/schema.sql` in the SQL Editor

---

## Usage Walkthrough

### Step 1 — Login
- Open `http://localhost:5173`
- Enter your Telegram phone number (with country code, e.g. `+91 9876543210`)
- Click **"Send OTP"** — you'll receive a code on Telegram
- Enter the OTP and click **"Verify & Login"**

### Step 2 — Find Groups
- On the Dashboard, enter an iGaming brand or keyword (e.g. `1xbet`, `betway affiliate`, `dream11 promoter`)
- Click **"Find Groups"** — AI expands your keyword into 5 search terms and finds relevant Telegram groups
- Review the group cards and **select** the ones you want to analyze

### Step 3 — Analyze Candidates
- Click **"Analyze Selected Groups"**
- The tool fetches the last 100 messages from each group and sends them to the selected AI model
- AI scores each user from 1–10 based on affiliate marketing potential
- You're automatically redirected to the Candidates page

### Step 4 — Review Candidates
- Browse the scored candidate list (filtered to score ≥ 6 by default)
- See AI reasoning and sample messages for each candidate
- Use the score filter to focus on high-potential candidates (8+)

### Step 5 — Send Outreach
- Click **"📨 Outreach"** on any candidate
- Edit the pre-filled outreach message template as needed
- Click **"Send Message"** — the DM is sent via your Telegram account
- The outreach is logged in Supabase

### Step 6 — View History
- Navigate to **"📬 Outreach History"**
- See all sent messages with timestamps, candidate usernames, and group sources

---

## Project Structure

```
/
├── backend/
│   ├── main.py                  # FastAPI app entry
│   ├── requirements.txt
│   ├── .env.example
│   ├── routers/
│   │   ├── auth.py              # Telegram OTP login/logout
│   │   ├── groups.py            # Search groups + fetch messages
│   │   ├── candidates.py        # AI analysis + list candidates
│   │   └── outreach.py          # Send DM + outreach history
│   └── lib/
│       ├── telegram_client.py   # Telethon wrapper
│       ├── gemini.py            # Gemini AI wrapper
│       └── supabase_client.py   # Supabase client
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   ├── Candidates.jsx
│       │   └── Outreach.jsx
│       └── components/
│           ├── Navbar.jsx
│           ├── GroupCard.jsx
│           ├── CandidateCard.jsx
│           ├── OutreachModal.jsx
│           └── Toast.jsx
├── supabase/
│   └── schema.sql
└── README.md
```

---

## Important Notes

> ⚠️ **Telegram Terms of Service:** Use this tool responsibly. Sending unsolicited messages in bulk may violate [Telegram's ToS](https://telegram.org/tos). This tool is intended for legitimate HR recruitment purposes only.

> 🔐 **Privacy:** Session strings are stored in Supabase and used to authenticate Telegram API calls. Keep your `SECRET_KEY` and Supabase credentials secure.

> 📱 **Phone Number:** The phone number used to log in must be an active Telegram account. Standard Telegram rate limits apply to group searches and message sends.

> 🤖 **AI Accuracy:** AI scoring is based on message context and may not be 100% accurate. Always review candidates manually before outreach.
