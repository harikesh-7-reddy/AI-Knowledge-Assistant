"""Safe Gemini API diagnostic; this script never prints the API key.

Run from the backend folder:
    python test_enterprise_brain_gemini.py
"""
from __future__ import annotations

import sys
import httpx

from app.config import (
    GEMINI_API_KEY,
    GEMINI_API_KEY_SOURCE,
    GEMINI_CHAT_MODEL,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_EMBEDDING_DIMENSION,
)
from app.knowledge import _gemini_request, create_embeddings


def show_error(exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            error = exc.response.json().get("error", {})
            print(f"HTTP status: {exc.response.status_code}")
            print(f"API error code: {error.get('status') or error.get('code') or 'unknown'}")
            print(f"API message: {str(error.get('message') or 'Request rejected')[:350]}")
        except Exception:
            print(f"HTTP status: {exc.response.status_code}")
    elif isinstance(exc, httpx.TimeoutException):
        print("Request timed out")
    elif isinstance(exc, httpx.RequestError):
        print(f"Network error: {type(exc).__name__}")
    else:
        print(f"Error: {type(exc).__name__}: {str(exc)[:250]}")


def main() -> int:
    print("Enterprise Brain - Gemini diagnostics")
    print(f"API key loaded: {bool(GEMINI_API_KEY)}")
    print(f"Key source: {GEMINI_API_KEY_SOURCE}")
    print(f"Key format hint: {'AIza...' if GEMINI_API_KEY.startswith('AIza') else ('configured' if GEMINI_API_KEY else 'missing')}")
    print(f"Chat model: {GEMINI_CHAT_MODEL}")
    print(f"Embedding model: {GEMINI_EMBEDDING_MODEL}")
    print(f"Embedding dimension: {GEMINI_EMBEDDING_DIMENSION}")

    if not GEMINI_API_KEY:
        print("\nNo key configured. Add GEMINI_API_KEY to backend/.env.")
        return 2

    print("\n1) Testing embeddings...")
    try:
        vectors = create_embeddings(["Enterprise Brain Gemini embedding diagnostic."], strict=True)
        vector = vectors[0]
        assert vector is not None and len(vector) == GEMINI_EMBEDDING_DIMENSION
        print(f"Embeddings: PASS ({len(vector)} dimensions)")
    except Exception as exc:
        print("Embeddings: FAILED")
        show_error(exc)
        embedding_ok = False
    else:
        embedding_ok = True

    print("\n2) Testing chat generation...")
    try:
        response = _gemini_request(GEMINI_CHAT_MODEL, "generateContent", {
            "contents": [{"role": "user", "parts": [{"text": "Reply with exactly: Enterprise Brain Gemini connection successful."}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 40},
        }, timeout=45)
        candidates = response.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
        text = " ".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise RuntimeError("Gemini returned no text candidate. Check model access or safety feedback.")
        print("Chat generation: PASS")
        print(f"Sample response: {text[:180]}")
        chat_ok = True
    except Exception as exc:
        print("Chat generation: FAILED")
        show_error(exc)
        chat_ok = False

    if embedding_ok and chat_ok:
        print("\nBoth Gemini checks passed.")
        return 0
    print("\nOne or more Gemini checks failed. Check key, free-tier quota, region and model access.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
