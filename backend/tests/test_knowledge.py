from app.knowledge import chunk_document, lexical_scores, retrieve_chunks


def test_chunk_document_preserves_page_numbers():
    text = "A sentence about leave policy. " * 120
    chunks = chunk_document([{"page_number": 4, "text": text}], max_chars=250, overlap=35)
    assert len(chunks) > 1
    assert all(chunk["page_number"] == 4 for chunk in chunks)
    assert all(chunk["content"] for chunk in chunks)


def test_lexical_retrieval_finds_relevant_passage():
    chunks = [
        {"content": "Employees receive 18 days of annual leave each calendar year.", "title": "Handbook", "document_id": 1, "page_number": 2},
        {"content": "Protected branches require peer review and automated checks.", "title": "Engineering", "document_id": 2, "page_number": 1},
    ]
    scores = lexical_scores("How many annual leave days do employees receive?", chunks)
    assert scores[0] > scores[1]
    results = retrieve_chunks("annual leave days", chunks)
    assert results
    assert results[0]["document_id"] == 1


def test_irrelevant_question_returns_no_retrieval():
    chunks = [{"content": "Employees receive 18 days of annual leave.", "title": "Handbook", "document_id": 1}]
    assert retrieve_chunks("What is the cafeteria lunch menu?", chunks) == []


def test_inflected_words_match_but_single_generic_overlap_does_not():
    from app.knowledge import lexical_scores

    passages = [
        {"content": "The company conducts a compensation review once each year."},
        {"content": "Employee relations cases are managed through the approved process."},
    ]
    scores = lexical_scores("How often is compensation reviewed?", passages)
    assert scores[0] > scores[1]
    unrelated = lexical_scores("What is the engineering release process?", [passages[1]])
    assert unrelated == [0.0]


def test_mixed_embedding_records_fall_back_without_dropping_older_documents():
    chunks = [
        {"content": "Annual leave is 18 days per year.", "document_id": 1, "embedding_json": None},
        {"content": "Protected branch releases require an approved review.", "document_id": 2, "embedding_json": '[0.1, 0.2]'},
    ]
    results = retrieve_chunks("annual leave days", chunks)
    assert results
    assert results[0]["document_id"] == 1


def test_gemini_embedding_request_uses_documented_embed_content_shape(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(knowledge, "GEMINI_EMBEDDING_DIMENSION", 3)
    captured = {}

    def fake_request(model, method, payload, timeout=45.0):
        captured.update(model=model, method=method, payload=payload)
        return {"embedding": {"values": [0.1, 0.2, 0.3]}}

    monkeypatch.setattr(knowledge, "_gemini_request", fake_request)
    vectors = knowledge.create_embeddings(["A policy passage"], task_type="RETRIEVAL_DOCUMENT", strict=True)

    assert vectors == [[0.1, 0.2, 0.3]]
    assert captured["model"] == knowledge.GEMINI_EMBEDDING_MODEL
    assert captured["method"] == "embedContent"
    assert captured["payload"]["content"]["parts"][0]["text"] == "A policy passage"
    assert captured["payload"]["embedContentConfig"]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert captured["payload"]["embedContentConfig"]["outputDimensionality"] == 3


def test_gemini_answer_requires_valid_source_citation(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(
        knowledge,
        "_gemini_request",
        lambda *args, **kwargs: {
            "candidates": [{"content": {"parts": [{"text": "Employees receive 18 days of leave [S1]."}]}}]
        },
    )
    answer, mode = knowledge.generate_answer(
        "What is the annual leave policy?",
        [{"source_id": "S1", "title": "Employee Handbook", "page_number": 1, "content": "Full-time employees receive 18 days of annual leave."}],
    )
    assert mode == "ai_generated"
    assert "[S1]" in answer


def test_gemini_answer_with_unknown_citation_falls_back(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(
        knowledge,
        "_gemini_request",
        lambda *args, **kwargs: {
            "candidates": [{"content": {"parts": [{"text": "The policy gives 30 days [S99]."}]}}]
        },
    )
    answer, mode = knowledge.generate_answer(
        "What is the annual leave policy?",
        [{"source_id": "S1", "title": "Employee Handbook", "page_number": 1, "content": "Full-time employees receive 18 days of annual leave."}],
    )
    assert mode == "local_evidence"
    assert "[S1]" in answer


def test_old_embedding_dimensions_fall_back_to_lexical(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(knowledge, "create_embeddings", lambda *args, **kwargs: [[0.1, 0.2, 0.3]])
    chunks = [
        {
            "content": "Employees receive 18 days of annual leave each calendar year.",
            "document_id": 1,
            "embedding_json": "[0.1, 0.2]",  # Simulate legacy 2D vector from another provider.
        }
    ]
    result = knowledge.retrieve_chunks("annual leave days", chunks)
    assert result
    assert result[0]["document_id"] == 1


def _vector_at_cosine(score: float) -> str:
    import json
    import math

    return json.dumps([score, math.sqrt(max(0.0, 1.0 - score * score))])


def test_vector_search_rejects_nearest_neighbors_without_topic_overlap(monkeypatch):
    """Out-of-domain questions must not be answered from weak nearest neighbors."""
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(knowledge, "create_embeddings", lambda *args, **kwargs: [[1.0, 0.0]])
    chunks = [
        {
            "content": "The company conducts a compensation review once each year.",
            "document_id": 1,
            "embedding_json": _vector_at_cosine(0.57),
        },
        {
            "content": "Employees should record attendance using the approved company attendance system.",
            "document_id": 2,
            "embedding_json": _vector_at_cosine(0.56),
        },
        {
            "content": "Employees must remain reachable during agreed collaboration hours.",
            "document_id": 3,
            "embedding_json": _vector_at_cosine(0.52),
        },
    ]

    assert knowledge.retrieve_chunks("What is the company's cafeteria menu?", chunks) == []


def test_vector_search_keeps_relevant_remote_work_and_drops_unrelated_docs(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(knowledge, "create_embeddings", lambda *args, **kwargs: [[1.0, 0.0]])
    relevant = {
        "content": "Employees may work remotely when their role and team arrangements permit it. Remote-work arrangements should be agreed with the manager.",
        "document_id": 1,
        "title": "Employee Handbook",
        "embedding_json": _vector_at_cosine(0.70),
    }
    unrelated_hr = {
        "content": "The company conducts a compensation review once each year.",
        "document_id": 2,
        "title": "HR Confidential Guidelines",
        "embedding_json": _vector_at_cosine(0.61),
    }
    unrelated_engineering = {
        "content": "Releases are deployed through the approved CI/CD pipeline.",
        "document_id": 3,
        "title": "Engineering Developer Onboarding",
        "embedding_json": _vector_at_cosine(0.57),
    }

    results = knowledge.retrieve_chunks(
        "Summarise the company's remote work policy.",
        [relevant, unrelated_hr, unrelated_engineering],
    )

    assert [item["document_id"] for item in results] == [1]


def test_no_evidence_response_does_not_call_gemini(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(
        knowledge,
        "_gemini_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Gemini must not be called without evidence")),
    )

    answer, mode = knowledge.generate_answer("What is the cafeteria menu?", [])

    assert mode == "no_evidence"
    assert "couldn't find sufficient evidence" in answer.lower()


def test_local_fallback_does_not_claim_key_missing_when_gemini_is_configured(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    answer = knowledge._extractive_answer(
        "What is the remote work policy?",
        [{"source_id": "S1", "content": "Employees may work remotely when their role permits it."}],
    )

    assert "could not be citation-validated" in answer.lower()
    assert "configure gemini_api_key" not in answer.lower()


def test_gemini_system_prompt_preserves_policy_modality(monkeypatch):
    import app.knowledge as knowledge

    monkeypatch.setattr(knowledge, "GEMINI_API_KEY", "test-gemini-key")
    captured = {}

    def fake_request(model, method, payload, timeout=45.0):
        captured.update(payload=payload)
        return {"candidates": [{"content": {"parts": [{"text": "Remote work may be allowed where role and team arrangements permit it [S1]."}]}}]}

    monkeypatch.setattr(knowledge, "_gemini_request", fake_request)
    answer, mode = knowledge.generate_answer(
        "Summarise the remote work policy.",
        [{"source_id": "S1", "title": "Employee Handbook", "page_number": 1, "content": "Employees may work remotely when their role and team arrangements permit it."}],
    )

    instruction = captured["payload"]["systemInstruction"]["parts"][0]["text"].lower()
    assert mode == "ai_generated"
    assert "do not turn 'should' into 'must'" in instruction
    assert "may" in answer
