import pytest
from fastapi import HTTPException


def test_admin_reindex_updates_vectors_only_after_complete_gemini_result(monkeypatch):
    import app.main as main

    chunks = [
        {"chunk_id": 11, "document_id": 1, "content": "First passage"},
        {"chunk_id": 12, "document_id": 1, "content": "Second passage"},
        {"chunk_id": 21, "document_id": 2, "content": "Third passage"},
    ]
    updates = {}
    audit_events = []
    monkeypatch.setattr(main, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main, "get_all_chunks_for_reindex", lambda: chunks)
    monkeypatch.setattr(main, "create_embeddings", lambda texts, **kwargs: [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
    monkeypatch.setattr(main, "update_chunk_embeddings", lambda pairs: updates.update(dict(pairs)))
    monkeypatch.setattr(main, "insert_audit", lambda *args: audit_events.append(args))

    result = main.reindex_with_gemini({"id": 9})

    assert result["documents"] == 2
    assert result["chunks"] == 3
    assert updates == {11: [0.1, 0.2], 12: [0.3, 0.4], 21: [0.5, 0.6]}
    assert audit_events and audit_events[0][1] == "gemini_reindex"


def test_admin_reindex_does_not_write_partial_vectors_when_gemini_fails(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main, "get_all_chunks_for_reindex", lambda: [{"chunk_id": 11, "document_id": 1, "content": "Passage"}])
    monkeypatch.setattr(main, "create_embeddings", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Gemini unavailable")))
    update_called = []
    monkeypatch.setattr(main, "update_chunk_embeddings", lambda pairs: update_called.append(pairs))

    with pytest.raises(HTTPException) as exc:
        main.reindex_with_gemini({"id": 9})

    assert exc.value.status_code == 502
    assert update_called == []


def test_admin_reindex_requires_gemini_key(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "GEMINI_API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        main.reindex_with_gemini({"id": 9})
    assert exc.value.status_code == 503
