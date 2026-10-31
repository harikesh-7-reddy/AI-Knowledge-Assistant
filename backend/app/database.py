from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import DB_PATH, DATA_DIR


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','employee')),
                department TEXT NOT NULL DEFAULT 'General',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                extension TEXT NOT NULL,
                content_type TEXT NOT NULL,
                access_level TEXT NOT NULL CHECK(access_level IN ('public','department','private')),
                department TEXT NOT NULL DEFAULT 'General',
                owner_id INTEGER NOT NULL REFERENCES users(id),
                file_size INTEGER NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                page_number INTEGER,
                content TEXT NOT NULL,
                embedding_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_documents_access ON documents(access_level, department);
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                citation_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with db() as conn:
        return row_to_dict(conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with db() as conn:
        return row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def create_user(email: str, full_name: str, password_hash: str, role: str, department: str) -> dict[str, Any]:
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO users(email, full_name, password_hash, role, department, created_at) VALUES(?,?,?,?,?,?)",
            (email.strip().lower(), full_name.strip(), password_hash, role, department.strip() or "General", utc_now()),
        )
        user_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)


def insert_audit(user_id: int, action: str, detail: str) -> None:
    with db() as conn:
        conn.execute("INSERT INTO audit_logs(user_id, action, detail, created_at) VALUES(?,?,?,?)", (user_id, action, detail[:1000], utc_now()))


def store_document(
    *, title: str, original_filename: str, stored_filename: str, extension: str,
    content_type: str, access_level: str, department: str, owner_id: int,
    file_size: int, page_count: int, chunks: list[dict[str, Any]],
) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO documents(title, original_filename, stored_filename, extension, content_type,
               access_level, department, owner_id, file_size, page_count, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (title, original_filename, stored_filename, extension, content_type, access_level,
             department, owner_id, file_size, page_count, utc_now()),
        )
        document_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT INTO chunks(document_id, chunk_index, page_number, content, embedding_json) VALUES(?,?,?,?,?)",
            [(document_id, c["chunk_index"], c.get("page_number"), c["content"], json.dumps(c["embedding"]) if c.get("embedding") else None) for c in chunks],
        )
        return document_id


def visible_document_sql(user: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    if user["role"] == "admin":
        return "1=1", ()
    return (
        "(d.access_level = 'public' OR (d.access_level = 'department' AND d.department = ?) OR (d.access_level = 'private' AND d.owner_id = ?))",
        (user["department"], user["id"]),
    )


def list_documents_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    clause, params = visible_document_sql(user)
    with db() as conn:
        rows = conn.execute(
            f"""SELECT d.id, d.title, d.original_filename, d.extension, d.content_type, d.access_level,
                d.department, d.owner_id, u.full_name AS owner_name, d.file_size, d.page_count, d.created_at,
                (SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.id) AS chunk_count
                FROM documents d JOIN users u ON u.id = d.owner_id WHERE {clause} ORDER BY d.created_at DESC""", params
        ).fetchall()
        return [dict(r) for r in rows]


def get_document_for_user(document_id: int, user: dict[str, Any]) -> dict[str, Any] | None:
    clause, params = visible_document_sql(user)
    with db() as conn:
        row = conn.execute(f"SELECT d.* FROM documents d WHERE d.id = ? AND {clause}", (document_id, *params)).fetchone()
        return row_to_dict(row)


def get_accessible_chunks(user: dict[str, Any]) -> list[dict[str, Any]]:
    clause, params = visible_document_sql(user)
    with db() as conn:
        rows = conn.execute(
            f"""SELECT c.id AS chunk_id, c.document_id, c.chunk_index, c.page_number, c.content,
                c.embedding_json, d.title, d.original_filename, d.access_level, d.department
                FROM chunks c JOIN documents d ON d.id = c.document_id WHERE {clause}""", params
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_chunks_for_reindex() -> list[dict[str, Any]]:
    """Return passages for an admin-triggered provider migration/reindex."""
    with db() as conn:
        rows = conn.execute(
            """SELECT c.id AS chunk_id, c.document_id, c.content, d.title
               FROM chunks c JOIN documents d ON d.id = c.document_id
               ORDER BY d.id, c.chunk_index"""
        ).fetchall()
        return [dict(row) for row in rows]


def update_chunk_embeddings(embeddings: list[tuple[int, list[float]]]) -> None:
    """Replace only vector columns; documents, chunks, permissions and history remain intact."""
    with db() as conn:
        conn.executemany(
            "UPDATE chunks SET embedding_json = ? WHERE id = ?",
            [(json.dumps(vector), chunk_id) for chunk_id, vector in embeddings],
        )


def save_chat(user_id: int, question: str, answer: str, citation_count: int) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO chat_messages(user_id, question, answer, citation_count, created_at) VALUES(?,?,?,?,?)",
            (user_id, question, answer, citation_count, utc_now()),
        )


def get_chat_history(user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT id, question, answer, citation_count, created_at FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]


def dashboard_stats(user: dict[str, Any]) -> dict[str, int]:
    clause, params = visible_document_sql(user)
    with db() as conn:
        docs = conn.execute(f"SELECT COUNT(*) n FROM documents d WHERE {clause}", params).fetchone()["n"]
        questions = conn.execute("SELECT COUNT(*) n FROM chat_messages WHERE user_id = ?", (user["id"],)).fetchone()["n"]
        chunks = conn.execute(f"SELECT COUNT(*) n FROM chunks c JOIN documents d ON d.id=c.document_id WHERE {clause}", params).fetchone()["n"]
        users = conn.execute("SELECT COUNT(*) n FROM users WHERE is_active=1").fetchone()["n"] if user["role"] == "admin" else 0
        return {"documents": int(docs), "chunks": int(chunks), "questions": int(questions), "users": int(users)}


def admin_users() -> list[dict[str, Any]]:
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT id,email,full_name,role,department,is_active,created_at FROM users ORDER BY created_at DESC").fetchall()]


def admin_audit(limit: int = 100) -> list[dict[str, Any]]:
    with db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT a.id,a.action,a.detail,a.created_at,u.email,u.full_name FROM audit_logs a JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT ?", (limit,)
        ).fetchall()]


def delete_document(document_id: int) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
        return result
