from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_SECRET, JWT_TTL_HOURS
from .database import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def create_access_token(user: dict[str, Any]) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(user["id"]), "iat": now, "exp": now + JWT_TTL_HOURS * 3600}
    message = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    return f"{message}.{_b64(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        message = f"{header_b64}.{payload_b64}"
        expected = _b64(hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature_b64):
            raise ValueError("Invalid token signature")
        payload_raw = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_raw.encode()))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    payload = decode_access_token(credentials.credentials)
    user = get_user_by_id(int(payload["sub"]))
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return user


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
