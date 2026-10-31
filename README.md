# Enterprise Brain — AI Knowledge Assistant

**Challenge 02 submission | A permission-aware company knowledge assistant with retrieval, source citations and evidence-aware answers.**

Enterprise Brain lets an organisation upload internal documents and ask natural-language questions. It extracts and indexes document passages, searches only documents the signed-in user is allowed to access, and returns answers with inspectable source passages. When evidence is missing, it says so instead of inventing a policy.

## What is implemented

- **Document ingestion:** PDF, DOCX, TXT and Markdown uploads; text extraction; page-aware PDF citations; overlapping passage chunking.
- **Gemini retrieval-augmented answering:** Gemini embeddings (`gemini-embedding-001`) and generated answers (`gemini-3.6-flash`) when a Gemini API key is configured. Without a key or when the service is unavailable, the application uses a conservative local lexical evidence fallback.
- **Citations:** every response includes source document title, filename, page (when available), relevance and the exact retrieved passage.
- **Missing-evidence behaviour:** questions with no sufficiently relevant accessible passages return an explicit insufficient-evidence response.
- **Access control:** public, department-restricted and private documents. Filtering happens in the backend SQL query **before** passages are ranked or sent to Gemini. Downloads enforce the same rule.
- **Authentication:** signed bearer tokens, salted PBKDF2 password hashes and active-account checks.
- **Admin console:** create users, assign roles/departments, upload/delete documents, inspect audit events and rebuild embeddings for existing passages.
- **Audit history:** sign-ins, document uploads/downloads/deletions, knowledge questions and Gemini reindex actions are recorded.
- **Data-preserving provider migration:** the reindex endpoint updates only `chunks.embedding_json`. It does not delete documents, users, permissions, chat history, or audit records.
- **Demo data:** a general employee handbook, HR-only guidelines and Engineering-only onboarding notes are created on first startup.
- **Responsive UI:** React workspace with chat, document library and admin console.

## Technology

| Layer | Implementation |
|---|---|
| Frontend | React 18, Vite, custom responsive CSS |
| API | Python, FastAPI, Pydantic |
| Storage | SQLite (users, documents, passages, chats, audit events) |
| Document parsing | PyMuPDF, python-docx, Python text decoding |
| Embeddings | Gemini `gemini-embedding-001` with 3072-dimensional vectors |
| Generation | Gemini `gemini-3.6-flash` via the Gemini Developer REST API |
| Retrieval fallback | Weighted lexical search when embeddings are unavailable or incompatible |
| Authentication | HMAC-signed bearer token, PBKDF2-SHA256 password hashes |

## Quick start (Windows PowerShell)

Prerequisites: Python 3.11+ and Node.js 20+.

1. Open a terminal in the project folder.
2. Start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

3. Open a second terminal and start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

4. Open **http://localhost:5173**. API docs are at **http://localhost:8000/docs**.

## Retrieval quality and missing-evidence behavior

The current retrieval pipeline is precision-first. A vector candidate with lexical topic support must reach 0.58 cosine similarity; a vector-only candidate with no lexical anchor must reach 0.72. If no passage passes, the API returns `mode: no_evidence` and `evidence_found: false` rather than showing unrelated HR/Engineering passages for an unsupported question. Policy wording is also protected: generated answers must not change “should” into “must” or otherwise strengthen/weaken the source. See [the retrieval fix notes](docs/RETRIEVAL_QUALITY_FIX.md).

## Configure Google Gemini

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. From the `backend` folder, copy `.env.example` to `.env` if you do not already have a `.env` file.
3. Edit `backend/.env` and set:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_CHAT_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSION=3072
JWT_SECRET=replace-with-a-long-random-secret
```

4. Restart the backend and run the provider test from the `backend` folder:

```powershell
python test_enterprise_brain_gemini.py
```

Expected: `Embeddings: PASS` and `Chat generation: PASS`.

The public health endpoint at `http://localhost:8000/api/health` should report `ai_mode: gemini` and `ai_provider: google_gemini`. This reports that a key is configured; the diagnostic verifies that the provider accepts it.

### Re-embed existing documents without losing data

Documents indexed before the Gemini key was configured may have no vectors or vectors from a different embedding model. Sign in as the administrator, open **Admin console**, and click **Rebuild embeddings**. The application recomputes vectors for existing passages and updates only their vector column. It preserves document records, original uploaded files, user accounts, roles, access levels, question history and audit logs. Do not delete the database or the `backend/data` folder during this migration.

If the API key is not configured, the app still works in local evidence mode using lexical retrieval and citation passages.

> **Free-tier data notice:** Google’s Gemini API pricing documentation says content submitted on the Free Tier may be used to improve Google products. Use synthetic/demo documents for the free-tier challenge demonstration; do not send confidential or regulated company records to a free-tier API. Google states paid-tier data is not used to improve its products. Check current terms, model availability and quotas before deployment.

## Existing project upgrade (Windows)

To apply this release over an existing Enterprise Brain folder:

1. Stop the backend and frontend.
2. Extract this project into the existing project folder and choose **Replace files** when prompted. Do not delete `backend/data` or the existing `.env` file.
3. In a PowerShell terminal inside `backend`, run:

```powershell
.\setup_gemini_env.ps1
```

This helper backs up your `.env`, removes obsolete OpenAI setting names, preserves unrelated settings such as `JWT_SECRET`, `DATA_DIR` and `CORS_ORIGINS`, and adds Gemini model settings. It does not copy an OpenAI key into the Gemini setting. Add the Google AI Studio key to `GEMINI_API_KEY` in `.env`.
4. Install/update dependencies and restart the API. Open Admin console and rebuild embeddings once.

The ZIP intentionally excludes `.env`, local databases and uploaded user files. Overlaying the source files on your existing project therefore keeps those local files untouched.

## Demo accounts

The first startup creates these accounts and sample documents. Change or remove demo accounts before any real deployment.

| Role | Email | Password | Visible sample documents |
|---|---|---|---|
| Administrator | `admin@example.com` | `AdminDemo123!` | All documents |
| HR employee | `hr@example.com` | `HrDemo123!` | Public + HR department |
| Engineering employee | `engineering@example.com` | `EngDemo123!` | Public + Engineering department |
| General employee | `employee@example.com` | `Employee123!` | Public documents only |

## Permission demonstration

1. Sign in as `hr@example.com` and ask: **“What is the compensation review cycle?”** The HR guidelines should be cited.
2. While signed in as HR, ask: **“What is the engineering release process?”** HR must not retrieve the Engineering-only document.
3. Sign in as `engineering@example.com` and ask the engineering release question. The Engineering onboarding passage should be cited.
4. Sign in as `employee@example.com` and open the document library. Only the public handbook should appear.
5. Sign in as administrator, upload a document, rebuild embeddings, and inspect the audit events.

## Docker

From the project root, set `GEMINI_API_KEY` and `JWT_SECRET` in the shell or environment, then run:

```bash
docker compose up --build
```

Open **http://localhost:5173**. The API is available at **http://localhost:8000**. Uploaded files and SQLite data persist in the `enterprise_brain_data` Docker volume.

## API overview

All endpoints except health and login require `Authorization: Bearer <access_token>`.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Service status and Gemini configuration |
| POST | `/api/auth/login` | Public | Authenticate and return token |
| GET | `/api/auth/me` | Signed-in | Current user |
| GET | `/api/dashboard/stats` | Signed-in | Accessible workspace counts |
| GET | `/api/documents` | Signed-in | List only accessible documents |
| POST | `/api/documents` | Admin | Upload and index a document |
| GET | `/api/documents/{id}/download` | Signed-in + document permission | Secure original-file download |
| DELETE | `/api/documents/{id}` | Admin | Delete document and indexed passages |
| POST | `/api/chat` | Signed-in | Ask a question with citations |
| GET | `/api/chat/history` | Signed-in | Current user's question history |
| GET | `/api/admin/users` | Admin | List workspace members |
| POST | `/api/admin/users` | Admin | Create a member |
| GET | `/api/admin/audit` | Admin | Recent audit events |
| POST | `/api/admin/reindex` | Admin | Re-embed existing passages with Gemini, preserving all other data |

## Permission model

- `public`: any authenticated workspace member.
- `department`: users whose department exactly matches the document's department, plus administrators.
- `private`: the uploader and administrators.
- Administrators can view all documents and manage accounts.

The backend builds the visibility condition in SQL and uses it for document lists, chunk retrieval and downloads. The UI is not treated as the security boundary. A forbidden or non-existent document download returns the same `404 Document not found` response to reduce document-ID enumeration.

## Automated tests

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The automated suite covers chunking, retrieval, citation fallback, permissions and password hashing. Provider calls are verified separately with `python test_enterprise_brain_gemini.py`.

## Project documentation

- `docs/PROJECT_REPORT.md` — submission project report.
- `docs/ARCHITECTURE.md` — architecture and data flow.
- `docs/TEST_PLAN.md` — functional and security test cases.
- `docs/DEMO_SCRIPT.md` — suggested live demonstration.
- `docs/PRESENTATION_OUTLINE.md` — slide-by-slide presentation content.
- `docs/GEMINI_SETUP.md` — provider configuration, migration and troubleshooting.
#   A I - K n o w l e d g e - A s s i s t a n t  
 