# Presentation Outline — Enterprise Brain

## Slide 1 — Title
**Enterprise Brain: AI Knowledge Assistant**  
Challenge 02 · A private, evidence-led knowledge assistant for organisations.

## Slide 2 — Problem
- Organisational knowledge is spread across PDF, DOCX and text files.
- Employees spend time locating the correct policy or procedure.
- Generic chatbot responses may be unsupported or reveal restricted information.

## Slide 3 — Proposed solution
- Upload and index company documents.
- Ask questions in natural language.
- Retrieve relevant passages and generate evidence-grounded answers.
- Display document, page and quoted passage citations.
- Explicitly acknowledge missing evidence.

## Slide 4 — System architecture
React frontend → FastAPI → authentication and permission filter → document chunks / retrieval → optional embeddings and LLM → answer with citations.

## Slide 5 — Working model
1. Upload a document.
2. Extract text and retain page metadata.
3. Split text into overlapping chunks and index them.
4. Authenticate the user and obtain department permissions.
5. Search only authorised chunks.
6. Generate the answer and display source passages.

## Slide 6 — Security and access control
- Public: all signed-in users.
- Department: matching department and administrators.
- Private: uploader and administrators.
- Permissions are enforced in backend SQL before retrieval and in download endpoints.
- Password hashes, signed sessions and audit logs.

## Slide 7 — Demonstration and evaluation
- Employee handbook question with citation.
- Unsupported question with a missing-evidence response.
- HR and Engineering users get different retrieval results.
- Admin uploads documents and manages workspace accounts.

## Slide 8 — Impact and future scope
- Faster access to internal knowledge.
- More transparent answers and easier verification.
- Less risk of cross-department information exposure.
- Future: OCR, SSO, object storage, PostgreSQL row-level security, document versioning and evaluation dashboards.
