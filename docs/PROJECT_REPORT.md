# Enterprise Brain: AI Knowledge Assistant

## 1. Abstract

Enterprise Brain is a permission-aware AI knowledge assistant designed to make organisational documents searchable through natural-language questions. The system ingests PDF, DOCX, TXT and Markdown documents, extracts their text, divides the text into overlapping passages, retrieves relevant evidence, and returns a response with citations to the source document and passage. A key design goal is that missing evidence is acknowledged rather than replaced with an unsupported answer. A second key goal is confidentiality: document visibility is enforced by the backend before content is searched or supplied to a language model.

## 2. Problem statement

Organisations store policies, procedures, onboarding material and operational guidance across many files. Employees may not know which file contains an answer, and conventional keyword search can be difficult to use. A general-purpose chatbot can produce convincing but unsupported statements and may expose information that the current user should not see. The challenge is to combine document retrieval, grounded answers, citations, evidence-aware behaviour and basic access control in one usable application.

## 3. Objectives

1. Provide a single interface for uploading and querying company documents.
2. Convert supported documents into searchable passages.
3. Retrieve evidence relevant to a user's question.
4. Cite document titles, page numbers where available, and exact supporting passages.
5. Acknowledge when the accessible documents do not contain sufficient evidence.
6. Enforce public, department and private document permissions on the server.
7. Give administrators tools to manage documents and users and review audit activity.

## 4. Proposed solution

The application follows a retrieval-augmented generation (RAG) pattern. During ingestion, the backend extracts text and creates overlapping chunks. When an Gemini API key is configured, chunks are embedded with `gemini-embedding-001` and stored with their records. At question time, the backend first obtains only the current user's accessible chunks from the database. It then ranks those passages using embedding similarity or a weighted lexical fallback. The top passages are provided to the answer generator, which is instructed to answer only from the supplied evidence and cite source identifiers. The UI displays the answer and the retrieved passages in separate citation cards.

Without an API key, the app remains runnable: it uses lexical ranking and returns matching evidence sentences. This mode is deliberately labelled as local evidence mode and does not pretend to be a generated AI response.

## 5. System modules

### 5.1 Authentication and identity

Users sign in with email and password. Passwords are salted and derived with PBKDF2-HMAC-SHA256. The API returns a signed, time-limited bearer token. Each protected request verifies the signature, expiry and active account.

### 5.2 Document ingestion

Administrators upload PDF, DOCX, TXT or Markdown. The system checks the file extension and size, stores the file using a generated server-side filename, extracts text, preserves PDF page numbers and splits the content into overlapping chunks. Each chunk is stored against its document. Failed extraction removes the partially stored file.

### 5.3 Retrieval and answer generation

The API filters chunks by the current user's document permissions before ranking them. Similarity retrieval uses saved embeddings when available and otherwise uses a weighted lexical score. Only sufficiently relevant passages are used. The answer generator receives a bounded context and instructions to avoid external knowledge and cite factual claims. If there are no sufficiently relevant passages, the service returns an explicit insufficient-evidence response.

### 5.4 Source citations

Each returned source includes a source ID, document title, original filename, page number when known, relevance score and the exact retrieved passage. The frontend displays each passage as a source card so a user can verify the evidence.

### 5.5 Permission management

The application provides three access levels:

- Public: visible to all authenticated users.
- Department: visible to members of the matching department and administrators.
- Private: visible to the uploader and administrators.

Administrators can create employee or administrator accounts and assign departments. The same access rule is used by document listing, chunk retrieval and file download routes.

### 5.6 Audit logging

The system records sign-ins, document upload/download/deletion events and knowledge questions. Administrators can inspect recent activity from the admin console.

## 6. Architecture

The frontend is a React single-page application. It communicates with a FastAPI backend over JSON and multipart HTTP endpoints. The backend uses SQLite for identity, document metadata, passage chunks, chat history and audit events; original uploaded files are stored in a private server-side directory. Document parsing is handled by PyMuPDF and python-docx. Optional model calls are made from the backend only, so provider credentials are never placed in browser code.

## 7. Security considerations

- Authentication is required for document and chat APIs.
- Passwords are not stored in plaintext.
- Uploaded filenames are not used as storage paths; generated names prevent path traversal.
- File size and extension are checked on upload.
- Access control is applied before retrieval and model context construction.
- Download routes repeat the document permission check.
- The frontend does not decide whether a user is authorised; it only displays backend-approved results.
- API credentials and signing secrets are environment configuration, not frontend values.

## 8. Demonstration data

The first startup seeds three clearly labelled sample knowledge documents:

1. Employee Handbook — public to all users.
2. HR Confidential Guidelines — HR department and administrators.
3. Engineering Developer Onboarding — Engineering department and administrators.

The seeded material is fictional demonstration content and must not be represented as an actual organisation's policies.

## 9. Expected outcomes

The user can ask questions in natural language, receive a grounded answer or evidence summary, inspect cited passages, and access only the documents authorised for their account. Administrators can upload documents, create members and review audit activity. The sample workspace demonstrates that two users asking the same question can receive different retrieval results based on their department permissions.

## 10. Limitations and future enhancements

The prototype uses SQLite and local disk storage, has no OCR for scanned PDFs, and relies on a configured model API for generated answers. Future improvements include PostgreSQL with row-level security, object storage, OCR, SSO/OIDC, fine-grained group permissions, automated evaluation, stronger audit retention, document versioning, malware scanning, streaming answers and deployment monitoring.

## 11. Conclusion

Enterprise Brain demonstrates the core challenge requirements in an integrated prototype: document-based question answering, source citations, explicit missing-evidence behaviour and server-enforced document permissions. The same permission rules are applied to retrieval and downloads, ensuring that inaccessible passages are excluded before the assistant prepares a response.
