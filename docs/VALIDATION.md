# Validation notes — Gemini edition

This edition migrates the optional model provider from OpenAI to Google Gemini. Source-level checks and offline tests are run when building the package; live Gemini calls must be verified on the user's machine with their own Google AI Studio key.

## What the package includes

- Gemini `generateContent` chat integration using `gemini-3.6-flash` by default.
- Gemini `embedContent` document/query embeddings using `gemini-embedding-001` with 3072 dimensions by default (overridable in `backend/.env`).
- Safe local evidence fallback when Gemini is unavailable or returns an answer without valid citations. Unsupported questions return an explicit no-evidence result without calling Gemini.
- An administrator-only reindex endpoint and Admin console button that update only passage embeddings and preserve all other SQLite data.
- Dimension checks that avoid comparing legacy OpenAI vectors with Gemini vectors before the admin reindex is run.

## Local automated checks

- Backend offline suite: **21 passed** during package validation.
- Python source compilation: passed.
- Two non-blocking FastAPI deprecation warnings remain for the existing startup event handler.
- Live Gemini service behavior still depends on the user's API key, quota, and current model availability.

## Retrieval quality update

- Vector matches with lexical topic support must score at least 0.58 cosine similarity.
- Vector-only candidates with no lexical anchor must score at least 0.72. This precision-first gate rejects weak nearest-neighbor matches for out-of-domain questions such as a cafeteria-menu query against HR/Engineering documents.
- If no candidates pass either gate, the API returns `mode: no_evidence`, `evidence_found: false`, and does not call Gemini.
- Answer instructions explicitly preserve policy strength (for example, `should` must not be rewritten as `must`).

## Verification steps

1. Configure `GEMINI_API_KEY` in `backend/.env`.
2. Run `python test_enterprise_brain_gemini.py` from `backend`; both embedding and chat checks should pass.
3. Restart the backend and confirm `/api/health` reports `ai_mode: gemini`.
4. Sign in as Admin and use **Rebuild embeddings** to migrate existing passage vectors.
5. Test HR, Engineering, General Employee and Admin accounts against `docs/TEST_PLAN.md`.
6. Ask an unsupported question and verify the assistant reports insufficient evidence.

## Limitations

- Live Gemini API connectivity, free-tier quotas and model availability depend on the user's Google AI Studio project and cannot be verified inside this package build.
- The free tier can have low or changing request quotas. Google currently documents that Free Tier content may be used to improve Google products; do not process confidential company material with a free-tier key unless the organization has reviewed and accepted the applicable terms.
- Scanned PDFs still require OCR before upload; ordinary text-based PDFs are supported.
