# Enterprise Brain — Fresh Windows Setup

This is the complete source project for Challenge 02. It includes the React frontend, FastAPI backend, Gemini chat and embeddings, sample documents, demo accounts, automated tests, and project documentation.

## Before you delete your old folder

If you want to keep anything you uploaded in your old installation, copy the old `backend/data` folder somewhere safe first. It may contain your SQLite database and uploaded documents. This fresh ZIP includes sample documents and recreates demo accounts on first startup, but it cannot contain your private uploaded files or API key.

## 1. Extract the ZIP

Extract the whole `Enterprise_Brain_Gemini_Full_Project` folder to a simple path, for example:

`C:\Projects\Enterprise_Brain_Gemini_Full_Project`

Open PowerShell in that extracted folder.

## 2. Configure Gemini

1. Open `backend/.env.example`.
2. Copy it to a new file named `backend/.env`.
3. Open `backend/.env` and replace `your_google_ai_studio_key` with your Google AI Studio key.
4. Keep the configured model values unless your Gemini account requires another supported model:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_CHAT_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSION=3072
JWT_SECRET=replace-with-a-long-random-secret
JWT_TTL_HOURS=12
DATA_DIR=./data
DATABASE_PATH=./data/enterprise_brain.db
MAX_UPLOAD_MB=20
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Do not share the key or commit `backend/.env` to GitHub. Gemini free-tier terms may allow submitted content to be used to improve Google's products; use synthetic/demo documents for the free-tier demonstration, not confidential company files.

## 3. Start the backend

Open PowerShell in the project root and run:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Keep this terminal open. On first startup the backend creates `backend/data`, the SQLite database, four demo accounts, and three sample documents. It does not require you to upload the sample documents manually.

## 4. Start the frontend

Open a SECOND PowerShell terminal in the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

If Windows reports a locked npm cache (`EBUSY`), close extra terminals or Node processes and retry `npm install`. The React Vite plugin is already declared in `frontend/package.json`; do not install arbitrary packages globally.

## 5. Verify Gemini

Open a THIRD PowerShell terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python test_enterprise_brain_gemini.py
```

Both checks should pass:

- `Embeddings: PASS`
- `Chat generation: PASS`

Backend health is available at `http://localhost:8000/api/health`; API docs are at `http://localhost:8000/docs`.

## 6. Rebuild embeddings

After Gemini tests pass, sign in as Admin, open Admin console, and select **Rebuild embeddings**. This updates passage vectors using Gemini and preserves the existing documents, users, document permissions, chat history, and audit records in the current database.

## Demo login accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@example.com | AdminDemo123! |
| HR | hr@example.com | HrDemo123! |
| Engineering | engineering@example.com | EngDemo123! |
| General employee | employee@example.com | Employee123! |

These are demonstration credentials. Change them and set a unique JWT secret before any real deployment.

## Recommended challenge tests

1. As Admin, ask `Summarise the company's remote work policy.` It should return an AI answer with handbook citations.
2. Ask `What is the company's cafeteria menu?` The assistant should say there is insufficient evidence and should not cite HR or Engineering passages.
3. As HR, ask `What is the engineering release process?` It must not retrieve the Engineering-only document.
4. As Engineering, ask `What is the engineering release process?` It should cite the Engineering onboarding document.
5. As a General employee, confirm that only public documents are visible.

## Automated backend tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The package's backend test suite passed 21 tests during preparation. Live Gemini requests depend on your own key, account quota, region and model service availability.

## Important file locations

- `backend/.env.example` — template; copy to `.env` and add your key.
- `backend/app/` — backend application and retrieval logic.
- `backend/sample_docs/` — three synthetic demo source documents.
- `backend/data/` — created at runtime; database and uploads live here.
- `frontend/src/` — React user interface.
- `docs/` — project report, architecture, test plan, demo script and presentation outline.
