# Technical Architecture

## High-level data flow

```text
Administrator uploads a file
        |
        v
FastAPI upload validation --> private file storage
        |
        v
PDF / DOCX / TXT / MD text extraction
        |
        v
Chunking with overlap + page metadata
        |
        v
Optional embeddings --> SQLite documents + chunks

User question
        |
        v
JWT validation --> load user + department
        |
        v
SQL permission filter (public / matching department / owned private)
        |
        v
Rank only permitted chunks (embedding similarity or lexical score)
        |
        +---- no evidence ----> explicit insufficient-evidence response
        |
        v
LLM receives only top permitted passages (when API key configured)
        |
        v
Answer + source IDs + citation passage cards --> React UI
```

## Main data entities

- `users`: email, name, password hash, role, department, active flag.
- `documents`: title, original and generated storage filenames, access level, department, owner, file size, page count and upload time.
- `chunks`: document foreign key, chunk index, page number, passage text and optional embedding JSON.
- `chat_messages`: user, question, answer, citation count and timestamp.
- `audit_logs`: user, action, detail and timestamp.

## Permission predicate

For an administrator, all documents are visible. For a non-administrator, a document is visible only when at least one condition holds:

```sql
 d.access_level = 'public'
 OR (d.access_level = 'department' AND d.department = :user_department)
 OR (d.access_level = 'private' AND d.owner_id = :user_id)
```

This predicate is applied in the SQL query that obtains candidate chunks, before ranking and before model context is built. A separate permission-filtered lookup is also used by original-file downloads. A document that is unavailable and a document ID that does not exist intentionally return the same not-found response.

## Answer grounding

The generator is instructed to use only provided passages, cite valid source IDs, and preserve the strength of policy wording (for example, it must not turn “should” into “must”). Retrieval is precision-first: vector matches with lexical topic support must reach 0.58 cosine similarity; vector-only matches with no lexical anchor must reach 0.72. This rejects weak nearest-neighbor results for unsupported topics (for example, cafeteria-menu questions when no cafeteria document exists). When no chunks pass the threshold, the API returns `mode: no_evidence` with `evidence_found: false`, and no language-model call is made. If Gemini generation itself is temporarily unavailable, the local-evidence fallback says that synthesis is unavailable rather than incorrectly claiming the API key is missing.

## Runtime configuration

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | HMAC signing secret; replace for deployment |
| `JWT_TTL_HOURS` | Bearer token lifetime |
| `GEMINI_API_KEY` | Optional Gemini model and embedding access |
| `GEMINI_CHAT_MODEL` | Gemini chat model name |
| `GEMINI_EMBEDDING_MODEL` | Gemini embedding model name |
| `MAX_UPLOAD_MB` | Upload size limit |
| `DATA_DIR` | Database and upload storage root |
| `CORS_ORIGINS` | Allowed browser origins |
