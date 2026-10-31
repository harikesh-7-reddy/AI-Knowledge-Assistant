from __future__ import annotations

import os
from pathlib import Path

# Resolve the local backend directory explicitly. The previous implementation
# used load_dotenv() with its default search behavior and override=False. On
# Windows, a stale GEMINI_API_KEY inherited from the user/process environment
# could therefore win over the value the developer had just put in backend/.env.
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

try:
    from dotenv import dotenv_values, load_dotenv

    # backend/.env is authoritative for local development; this prevents stale
    # Windows process/user variables from overriding the key the user just set.
    _file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    _file_key = str(_file_values.get("GEMINI_API_KEY") or "").strip()
    load_dotenv(dotenv_path=ENV_FILE, override=True)
except ImportError:
    _file_key = ""

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if _file_key:
    GEMINI_API_KEY_SOURCE = "backend/.env"
elif GEMINI_API_KEY:
    GEMINI_API_KEY_SOURCE = "process environment"
else:
    GEMINI_API_KEY_SOURCE = "not configured"

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "enterprise_brain.db"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
JWT_SECRET = os.getenv("JWT_SECRET", "development-secret-change-this-before-deployment")
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "12"))
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_EMBEDDING_DIMENSION = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", "3072"))
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
