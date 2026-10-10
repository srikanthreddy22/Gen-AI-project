"""Lightweight persistent vector store using SQLite.
Stores document chunks and embeddings as JSON lists.
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Tuple
import math

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".vector_store.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            doc_id TEXT,
            doc_name TEXT,
            chunk_id TEXT PRIMARY KEY,
            chunk_index INTEGER,
            chunk_text TEXT,
            source_meta TEXT,
            embedding TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def init_db_at_path(path: str):
    """Create the chunks table in an arbitrary DB path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            doc_id TEXT,
            doc_name TEXT,
            chunk_id TEXT PRIMARY KEY,
            chunk_index INTEGER,
            chunk_text TEXT,
            source_meta TEXT,
            embedding TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_document_chunks(doc_id: str, doc_name: str, chunks: List[Dict[str, Any]]):
    conn = _get_conn()
    c = conn.cursor()
    for ch in chunks:
        c.execute(
            "REPLACE INTO chunks (doc_id, doc_name, chunk_id, chunk_index, chunk_text, source_meta, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                doc_name,
                ch["chunk_id"],
                ch.get("chunk_index", 0),
                ch["chunk_text"],
                json.dumps(ch.get("source_meta", {})),
                json.dumps(ch.get("embedding", [])),
            ),
        )
    conn.commit()
    conn.close()


def add_document_chunks_to_dbpath(db_path: str, doc_id: str, doc_name: str, chunks: List[Dict[str, Any]]):
    """Add chunks into the DB at db_path. Used for temporary DB preparation."""
    init_db_at_path(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for ch in chunks:
        c.execute(
            "REPLACE INTO chunks (doc_id, doc_name, chunk_id, chunk_index, chunk_text, source_meta, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                doc_name,
                ch["chunk_id"],
                ch.get("chunk_index", 0),
                ch["chunk_text"],
                json.dumps(ch.get("source_meta", {})),
                json.dumps(ch.get("embedding", [])),
            ),
        )
    conn.commit()
    conn.close()


def get_document_chunks(doc_id: str) -> List[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    rows = c.execute("SELECT chunk_id, chunk_index, chunk_text, source_meta, embedding FROM chunks WHERE doc_id=? ORDER BY chunk_index", (doc_id,)).fetchall()
    conn.close()
    out = []
    for cid, idx, text, meta, emb in rows:
        out.append({
            "chunk_id": cid,
            "chunk_index": idx,
            "chunk_text": text,
            "source_meta": json.loads(meta or "{}"),
            "embedding": json.loads(emb or "[]"),
        })
    return out


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def similarity_search(doc_id: str, query_embedding: List[float], top_k: int = 8, min_score: float = 0.0) -> List[Tuple[float, Dict[str, Any]]]:
    chunks = get_document_chunks(doc_id)
    scored = []
    for ch in chunks:
        score = _cosine(query_embedding, ch.get("embedding", []))
        if score >= min_score:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def delete_document_embeddings(doc_id: str):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    conn.commit()
    conn.close()


def atomic_replace_document(doc_id: str, src_db_path: str) -> None:
    """Atomically replace rows for `doc_id` in main DB with rows from src_db_path using ATTACH.

    This uses a transaction to DELETE old rows and INSERT new rows from the attached DB,
    providing an atomic swap for that document.
    """
    main_conn = _get_conn()
    try:
        cur = main_conn.cursor()
        # attach source DB
        cur.execute(f"ATTACH DATABASE ? AS tmpdb", (src_db_path,))
        # perform swap in transaction
        cur.execute("BEGIN")
        cur.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        cur.execute(
            "INSERT OR REPLACE INTO chunks (doc_id, doc_name, chunk_id, chunk_index, chunk_text, source_meta, embedding) SELECT doc_id, doc_name, chunk_id, chunk_index, chunk_text, source_meta, embedding FROM tmpdb.chunks WHERE doc_id=?",
            (doc_id,)
        )
        cur.execute("COMMIT")
    except Exception:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        try:
            cur.execute("DETACH DATABASE tmpdb")
        except Exception:
            pass
        main_conn.close()


init_db()
