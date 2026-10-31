# Live Demonstration Script (3–4 minutes)

## Opening (20 seconds)

“Enterprise Brain is a private AI knowledge assistant for company documents. Employees can ask questions in natural language, see the exact passages behind an answer, and only retrieve documents their account is permitted to access.”

## Demo 1 — Evidence and citations (45 seconds)

1. Sign in as `employee@example.com` with password `Employee123!`.
2. Ask: “What is the annual leave policy?”
3. Show the answer and the Employee Handbook citation card.
4. Point out the cited passage and page metadata.

Narration: “The assistant does not just return a response. It exposes the passage it used, so an employee can verify the answer.”

## Demo 2 — Missing evidence (25 seconds)

Ask: “What is the company cafeteria menu?”

Narration: “The uploaded knowledge base does not contain this information. Instead of guessing, the assistant explicitly says there is insufficient evidence.”

## Demo 3 — Document permissions (60 seconds)

1. Sign out and sign in as `hr@example.com` / `HrDemo123!`.
2. Ask: “How often is compensation reviewed?” Show the HR guideline citation.
3. Ask: “What is the engineering release process?” Show that the HR user receives no Engineering-only source.
4. Sign in as `engineering@example.com` / `EngDemo123!` and ask the release question. Show the Engineering citation.

Narration: “This is the key security design. The backend filters candidate passages by the user's department before retrieval and before any context reaches the AI model. The same permission check is applied to file downloads.”

## Demo 4 — Admin controls (45 seconds)

1. Sign in as `admin@example.com` / `AdminDemo123!`.
2. Open the document library and show all three sample documents.
3. Open Admin Console and show workspace members and recent audit activity.
4. Optionally upload a small text file and set its access to a department.

Narration: “Administrators can manage the knowledge base, create accounts, assign departments and review audit activity.”

## Closing (15 seconds)

“Enterprise Brain combines document-based question answering, traceable citations, evidence-aware responses and server-enforced permissions in one working prototype.”

**Presenter note:** The seeded handbook, HR and Engineering files are fictional demonstration data. Do not present them as real company policies. For generated AI synthesis, configure an API key before the demo; without it, the system clearly labels its evidence-only fallback mode.
