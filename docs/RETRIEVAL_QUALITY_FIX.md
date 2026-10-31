# Retrieval quality and missing-evidence fix

## What changed

- Replaced weak vector-nearest-neighbor acceptance with precision-first thresholds.
- A candidate needs cosine similarity of at least `0.58` when query terms also anchor it to the passage.
- A candidate with no lexical topic overlap needs at least `0.72` cosine similarity.
- If no candidate passes, retrieval returns an empty list. The chat API then returns `mode: no_evidence` and `evidence_found: false`; it does not send unrelated passages to Gemini.
- Lexical retrieval remains available when embeddings are missing, mismatched, or the Gemini embedding request is unavailable.
- Gemini instructions now explicitly preserve policy modality (`may`, `should`, `must`) rather than strengthening or weakening source statements.
- Local evidence fallback now distinguishes a missing key from a temporary Gemini generation failure.
- Existing SQL permission filtering remains upstream of retrieval. Only already-authorized chunks can be ranked or sent to Gemini.

## Regression coverage

The backend test suite includes cases for weak cafeteria-menu nearest neighbors being rejected, relevant remote-work passages being kept while unrelated HR/Engineering passages are removed, no-evidence answers avoiding Gemini calls, and correct `embedContent` response parsing.

Run from `backend`:

```powershell
python -m pytest -q
```
