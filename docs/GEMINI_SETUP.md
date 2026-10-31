# Gemini setup and data-preserving migration

## Get a Gemini API key

Create a key in [Google AI Studio](https://aistudio.google.com/apikey). Keep it in the backend only; never add it to React/Vite code or commit it to source control.

## Environment variables

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_CHAT_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSION=3072
```

Gemini uses the `generateContent` method for chat and the documented `embedContent` method for passage and question vectors. Document passages are embedded using `RETRIEVAL_DOCUMENT`; user questions are embedded using `RETRIEVAL_QUERY`. Both use the same embedding model and output dimension.

## Diagnostic

From `backend`:

```powershell
python test_enterprise_brain_gemini.py
```

This test prints whether the key is configured and checks both embedding and chat requests. It never prints the API key.

## Re-index existing passages

After switching from OpenAI vectors (or from lexical-only ingestion) to Gemini, sign in as an administrator and select **Admin console → Rebuild embeddings**. The endpoint:

1. Reads the existing extracted passage text.
2. Requests Gemini document embeddings one passage at a time using `embedContent`.
3. Updates only `chunks.embedding_json` after all batches succeed.
4. Records an audit event.

It does not change document IDs, uploaded files, access levels, department assignments, owners, users, chat history, or prior audit records. If an API batch fails, the operation stops before replacing any vectors.

The runtime detects embeddings of a mismatched dimension and uses lexical search rather than comparing incompatible vector spaces. This ensures old vectors do not corrupt results before the admin reindex is completed.

## Data protection warning

Google's published Gemini API pricing documentation currently indicates that Free Tier content may be used to improve Google products. The Paid Tier indicates that content is not used for that purpose. Use the free tier only with public/synthetic demonstration documents unless your organization has reviewed and accepted Google's current terms and data handling. Review the live [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [billing](https://ai.google.dev/gemini-api/docs/billing) documentation before production use.

## Common errors

- **401 / `API_KEY_INVALID`:** check the key in `backend/.env`; it must be a Google AI Studio Gemini key.
- **403 / permission or API disabled:** check that the key's Google AI Studio project is enabled for the Gemini API.
- **404 model not found:** verify the model names in the `.env` file against the current Gemini models list.
- **429 / `RESOURCE_EXHAUSTED`:** wait for the quota window to reset, reduce batch size or request frequency, and review the AI Studio rate limits for that project.
- **Local evidence still shown:** check backend logs. The system deliberately falls back to cited local passages if Gemini fails or returns an answer without valid source IDs.
