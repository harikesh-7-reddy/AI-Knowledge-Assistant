from __future__ import annotations

import json
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

from .config import ALLOWED_EXTENSIONS, CORS_ORIGINS, DATA_DIR, GEMINI_API_KEY, GEMINI_API_KEY_SOURCE, GEMINI_CHAT_MODEL, GEMINI_EMBEDDING_MODEL, MAX_UPLOAD_BYTES, UPLOAD_DIR
from .database import (
    admin_audit, admin_users, create_user, dashboard_stats, db, delete_document,
    get_accessible_chunks, get_all_chunks_for_reindex, get_chat_history, get_document_for_user, get_user_by_email,
    init_db, insert_audit, list_documents_for_user, save_chat, store_document, update_chunk_embeddings, utc_now,
)
from .knowledge import chunk_document, create_embeddings, extract_document, generate_answer, retrieve_chunks
from .security import create_access_token, get_current_user, hash_password, require_admin, verify_password

app = FastAPI(
    title="Enterprise Brain API",
    description="A permission-aware retrieval-augmented knowledge assistant with source citations.",
    version="1.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["admin", "employee"] = "employee"
    department: str = Field(default="General", min_length=1, max_length=80)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"], "email": user["email"], "full_name": user["full_name"],
        "role": user["role"], "department": user["department"], "is_active": bool(user["is_active"]),
    }


def _seed_data() -> None:
    from .config import BASE_DIR

    with db() as conn:
        count = conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    if count == 0:
        demo_users = [
            ("admin@example.com", "Demo Administrator", "AdminDemo123!", "admin", "IT"),
            ("hr@example.com", "HR Demonstration User", "HrDemo123!", "employee", "HR"),
            ("engineering@example.com", "Engineering Demonstration User", "EngDemo123!", "employee", "Engineering"),
            ("employee@example.com", "General Demonstration User", "Employee123!", "employee", "General"),
        ]
        for email, name, password, role, department in demo_users:
            create_user(email, name, hash_password(password), role, department)
    # Sample documents are inserted once, so a fresh install is immediately demonstrable.
    with db() as conn:
        document_count = conn.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"]
    if document_count == 0:
        admin = get_user_by_email("admin@example.com")
        if not admin:
            return
        samples = [
            ("Employee Handbook", "employee-handbook.txt", "public", "General"),
            ("HR Confidential Guidelines", "hr-confidential-guidelines.txt", "department", "HR"),
            ("Engineering Developer Onboarding", "engineering-onboarding.txt", "department", "Engineering"),
        ]
        sample_dir = BASE_DIR / "sample_docs"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        for title, filename, access_level, department in samples:
            source = sample_dir / filename
            if not source.exists():
                continue
            content = source.read_bytes()
            stored_name = f"{uuid.uuid4().hex}{source.suffix}"
            (UPLOAD_DIR / stored_name).write_bytes(content)
            blocks, pages = extract_document(UPLOAD_DIR / stored_name, source.suffix)
            pieces = chunk_document(blocks)
            vectors = create_embeddings([p["content"] for p in pieces])
            for piece, vector in zip(pieces, vectors):
                piece["embedding"] = vector
            store_document(
                title=title, original_filename=filename, stored_filename=stored_name,
                extension=source.suffix, content_type="text/plain", access_level=access_level,
                department=department, owner_id=admin["id"], file_size=len(content),
                page_count=pages, chunks=pieces,
            )


@app.on_event("startup")
def startup() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    _seed_data()


@app.get("/api/health")
def health() -> dict[str, Any]:
    configured = bool(GEMINI_API_KEY)
    key_hint = "AIza..." if GEMINI_API_KEY.startswith("AIza") else ("configured" if configured else "none")
    return {
        "status": "ok",
        "service": "Enterprise Brain API",
        "version": "1.1.0",
        # This means the key is configured; the Gemini diagnostic verifies API access.
        "ai_mode": "gemini" if configured else "local_evidence",
        "ai_provider": "google_gemini",
        "ai_key_configured": configured,
        "ai_key_source": GEMINI_API_KEY_SOURCE,
        "ai_key_format_hint": key_hint,
        "chat_model": GEMINI_CHAT_MODEL,
        "embedding_model": GEMINI_EMBEDDING_MODEL,
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    user = get_user_by_email(payload.email)
    if not user or not user["is_active"] or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    insert_audit(user["id"], "login", "User signed in")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": public_user(user)}


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return public_user(user)


@app.get("/api/dashboard/stats")
def stats(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, int]:
    return dashboard_stats(user)


@app.get("/api/documents")
def get_documents(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    return list_documents_for_user(user)


@app.post("/api/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    access_level: Literal["public", "department", "private"] = Form("public"),
    department: str = Form("General"),
    user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    original_filename = Path(file.filename or "uploaded-document").name
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Supported formats: PDF, DOCX, TXT and MD")
    if access_level == "department" and not department.strip():
        raise HTTPException(status_code=400, detail="Choose a department for department-restricted documents")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / stored_filename
    destination.write_bytes(content)
    try:
        blocks, page_count = extract_document(destination, extension)
        pieces = chunk_document(blocks)
        if not pieces:
            raise ValueError("No usable text could be extracted from this document")
        vectors = create_embeddings([piece["content"] for piece in pieces])
        for piece, vector in zip(pieces, vectors):
            piece["embedding"] = vector
        document_id = store_document(
            title=(title.strip() or Path(original_filename).stem)[:160],
            original_filename=original_filename, stored_filename=stored_filename,
            extension=extension, content_type=file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream",
            access_level=access_level, department=department.strip() or "General", owner_id=user["id"],
            file_size=len(content), page_count=page_count, chunks=pieces,
        )
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not process document: {exc}") from exc
    insert_audit(user["id"], "document_uploaded", f"Uploaded {original_filename} (access={access_level}, department={department})")
    return {"id": document_id, "title": title.strip() or Path(original_filename).stem, "chunk_count": len(pieces), "page_count": page_count, "message": "Document indexed successfully"}


@app.get("/api/documents/{document_id}/download")
def download_document(document_id: int, user: dict[str, Any] = Depends(get_current_user)) -> FileResponse:
    document = get_document_for_user(document_id, user)
    if not document:
        # Same response for missing and forbidden IDs prevents document enumeration.
        raise HTTPException(status_code=404, detail="Document not found")
    path = UPLOAD_DIR / document["stored_filename"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Original file is no longer available")
    insert_audit(user["id"], "document_downloaded", f"Downloaded document ID {document_id}")
    return FileResponse(path, filename=document["original_filename"], media_type=document["content_type"])


@app.delete("/api/documents/{document_id}")
def remove_document(document_id: int, user: dict[str, Any] = Depends(require_admin)) -> dict[str, str]:
    document = delete_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    (UPLOAD_DIR / document["stored_filename"]).unlink(missing_ok=True)
    insert_audit(user["id"], "document_deleted", f"Deleted document ID {document_id}")
    return {"message": "Document deleted"}


@app.post("/api/chat")
def ask_question(payload: ChatRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question")
    # Critical security boundary: get_accessible_chunks filters at SQL retrieval time,
    # before any passage is sent to the ranking or language model layer.
    allowed_chunks = get_accessible_chunks(user)
    retrieved = retrieve_chunks(question, allowed_chunks, top_k=5)
    sources = []
    for index, item in enumerate(retrieved, start=1):
        sources.append({
            "source_id": f"S{index}", "document_id": item["document_id"],
            "title": item["title"], "filename": item["original_filename"],
            "page_number": item.get("page_number"), "passage": item["content"],
            "relevance": item["score"], "department": item["department"],
        })
    answer, mode = generate_answer(question, [
        {"source_id": s["source_id"], "title": s["title"], "page_number": s["page_number"], "content": s["passage"]}
        for s in sources
    ])
    save_chat(user["id"], question, answer, len(sources))
    insert_audit(user["id"], "question_asked", f"Question: {question[:500]} | Retrieved passages: {len(sources)}")
    return {"answer": answer, "citations": sources, "mode": mode, "evidence_found": bool(sources), "created_at": utc_now()}


@app.get("/api/chat/history")
def chat_history(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    return get_chat_history(user["id"])


@app.get("/api/admin/users")
def users(_: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    return admin_users()


@app.post("/api/admin/users")
def add_user(payload: UserCreateRequest, admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    try:
        user = create_user(payload.email, payload.full_name, hash_password(payload.password), payload.role, payload.department)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    insert_audit(admin["id"], "user_created", f"Created {payload.role} account {payload.email} ({payload.department})")
    return public_user(user)


@app.get("/api/admin/audit")
def audit(_: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    return admin_audit()


@app.post("/api/admin/reindex")
def reindex_with_gemini(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Re-embed existing passages without deleting or recreating business data."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Configure GEMINI_API_KEY in backend/.env before reindexing")
    chunks = get_all_chunks_for_reindex()
    if not chunks:
        return {"documents": 0, "chunks": 0, "message": "There are no passages to reindex."}
    try:
        vectors = create_embeddings(
            [chunk["content"] for chunk in chunks],
            task_type="RETRIEVAL_DOCUMENT",
            strict=True,
        )
        if len(vectors) != len(chunks) or any(vector is None for vector in vectors):
            raise RuntimeError("Gemini did not return an embedding for every passage")
        # Apply the complete new vector set only after all provider calls succeed.
        update_chunk_embeddings([
            (chunk["chunk_id"], vector)
            for chunk, vector in zip(chunks, vectors)
            if vector is not None
        ])
    except Exception as exc:
        detail = str(exc)[:300]
        raise HTTPException(status_code=502, detail=f"Gemini reindex failed: {detail}") from exc
    documents = len({chunk["document_id"] for chunk in chunks})
    insert_audit(admin["id"], "gemini_reindex", f"Re-embedded {len(chunks)} passages across {documents} documents")
    return {
        "documents": documents,
        "chunks": len(chunks),
        "embedding_model": GEMINI_EMBEDDING_MODEL,
        "message": "Existing passages were re-embedded with Gemini. Documents, permissions, accounts and chat history were preserved.",
    }

