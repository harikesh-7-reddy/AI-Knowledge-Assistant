# Test Plan and Acceptance Criteria

## Functional tests

| ID | Test | Steps | Expected result |
|---|---|---|---|
| F-01 | Admin login | Sign in with demo admin | Workspace opens; Admin Console is visible |
| F-02 | HR login | Sign in with HR demo account | HR user is shown; Admin Console is hidden |
| F-03 | Employee handbook retrieval | Ask “What is the annual leave policy?” as any demo user | Answer/evidence summary cites Employee Handbook and displays the supporting passage |
| F-04 | Engineering retrieval | Ask “What is the engineering release process?” as Engineering | Engineering Onboarding source is cited |
| F-05 | Missing evidence | Ask an unrelated question, e.g. “What is the office cafeteria menu?” | Assistant explicitly says accessible documents do not contain sufficient evidence |
| F-06 | Upload | Admin uploads a readable TXT or PDF document | Success message; document appears in the admin's library and is searchable |
| F-07 | Create user | Admin creates an employee in a new department | User appears in members list and can sign in |
| F-08 | Audit history | Perform sign-in, query and upload | Corresponding events appear in Admin Console |
| F-09 | Unsupported extension | Attempt to upload an executable or unsupported file | API rejects it with HTTP 415 |
| F-10 | Oversized upload | Upload a file larger than configured limit | API rejects it with HTTP 413 |

## Permission and security tests

| ID | Test | Steps | Expected result |
|---|---|---|---|
| S-01 | HR can read HR document | Sign in as HR; ask “How often is compensation reviewed?” | HR Confidential Guidelines may be retrieved and cited |
| S-02 | Engineering cannot read HR doc | Sign in as Engineering; ask the same compensation question | HR passage is not in the retrieved sources; answer acknowledges missing evidence unless another accessible source supports it |
| S-03 | HR cannot read Engineering doc | Sign in as HR; ask about protected-branch reviews or release process | Engineering-only passage is not retrieved |
| S-04 | General user scope | Sign in as General employee; open library | Only public documents are listed |
| S-05 | Direct-download protection | Obtain a restricted document ID as admin; request its download using a general employee token | HTTP 404; no file bytes are returned |
| S-06 | Admin sees all docs | Sign in as admin; open library | All seeded documents are listed |
| S-07 | API admin boundary | Call `/api/admin/users` as an employee | HTTP 403 |
| S-08 | Unauthenticated request | Call `/api/documents` without bearer token | HTTP 401 |
| S-09 | Password storage | Inspect `users.password_hash` in SQLite | PBKDF2 hash is stored; plaintext password is absent |

## Demo acceptance criteria

1. The app starts with the documented commands.
2. The four seeded demo accounts can authenticate.
3. The three sample documents demonstrate public, HR-only and Engineering-only scope.
4. At least one answer displays a source passage and document name.
5. At least one unsupported question produces an explicit missing-evidence answer.
6. A restricted query from a different department does not expose the restricted source.

## Notes

The demo data is fictional. PDF citations preserve physical page numbers. DOCX/TXT/Markdown passages currently use page 1 because those formats do not provide a reliable rendered page map in this prototype. Scanned PDFs without a text layer are rejected with a clear message; OCR is a future enhancement.
