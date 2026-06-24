import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from routers import auth, groups, candidates, outreach

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    sys.exit("ERROR: SECRET_KEY environment variable is not set. Set it in your .env file.")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app = FastAPI(title="ACE2KING Candidate Finder", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="ace2king_session",
    max_age=86400 * 7,
    same_site="lax",
    https_only=False,
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(outreach.router, prefix="/api/outreach", tags=["outreach"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ACE2KING Candidate Finder"}
