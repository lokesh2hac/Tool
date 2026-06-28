import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from routers import auth, groups, candidates, outreach, api_keys
from routers import auto_scan
from routers import sessions
from routers.group_posts import router as group_posts_router  # 👈 direct import

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    sys.exit("ERROR: SECRET_KEY environment variable is not set.")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]

IS_PRODUCTION = os.getenv("RENDER", "") != ""

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
    same_site="none" if IS_PRODUCTION else "lax",
    https_only=IS_PRODUCTION,
)

# API Routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(outreach.router, prefix="/api/outreach", tags=["outreach"])
app.include_router(api_keys.router, prefix="/api/api-keys", tags=["api-keys"])
app.include_router(auto_scan.router, prefix="/api/auto-scan", tags=["auto-scan"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(group_posts_router, prefix="/api/group-posts", tags=["group-posts"])  # 👈 direct router

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ACE2KING Candidate Finder", "production": IS_PRODUCTION}

# --- Frontend static files (optional) ---
frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return None
        return FileResponse(os.path.join(frontend_dist, "index.html"))
