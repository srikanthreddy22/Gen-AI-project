"""Persistent ChromaDB storage for document chunks and semantic embeddings."""

import json
import logging
import math
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Mapping, Tuple

import chromadb
from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

from .embedding_service import get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "notebot_documents"
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEFAULT_PERSIST_DIRECTORY = os.path.join(_BACKEND_DIR, "data", "chroma")
_LEGACY_DB_PATH = os.path.join(_BACKEND_DIR, ".vector_store.db")
_clients: Dict[str, Tuple[Any, Any]] = {}
_clients_lock = threading.Lock()


class VectorStoreError(RuntimeError):
    """Raised when vector data cannot be safely read or written."""


def _persist_directory() -> str:
    configured = os.getenv("CHROMA_PERSIST_DIRECTORY")
    if not configured and has_app_context():
        configured = current_app.config.get("CHROMA_PERSIST_DIRECTORY")
    return os.path.abspath(configured or _DEFAULT_PERSIST_DIRECTORY)


def _where_document(doc_id: str, user_id: str | None = None) -> Dict[str, Any]:
    filters: List[Dict[str, Any]] = [{"document_id": doc_id}]
    if user_id is not None:
        filters.append({"user_id": str(user_id)})
    return filters[0] if len(filters) == 1 else {"$and": filters}


def _get_collection():
    persist_directory = _persist_directory()
    with _clients_lock:
        cached = _clients.get(persist_directory)
        if cached is None:
            os.makedirs(persist_directory, exist_ok=True)
            client = chromadb.PersistentClient(path=persist_directory)
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            _clients[persist_directory] = (client, collection)
        else:
            client, collection = cached

    if os.getenv("NOTEBOT_DISABLE_LEGACY_VECTOR_MIGRATION", "").lower() not in {"1", "true", "yes"}:
        _migrate_legacy_store_once(collection, persist_directory)
    return collection


def _lookup_legacy_owners(doc_ids: List[str]) -> Dict[str, str]:
    if not doc_ids or not has_app_context():
        return {}
    try:
        from ..models import Document

        owners: Dict[str, str] = {}
        for offset in range(0, len(doc_ids), 500):
            batch = doc_ids[offset:offset + 500]
            rows = Document.query.filter(Document.vector_id.in_(batch)).all()
            owners.update({
                row.vector_id: str(row.user_id)
                for row in rows
                if row.user_id is not None
            })
        return owners
    except SQLAlchemyError:
        from ..extensions import db

        db.session.rollback()
        logger.exception(
            "Could not map legacy vector documents to owners; imported records will remain "
            "inaccessible to user-scoped retrieval until they are reindexed."
        )
        return {}


def _read_legacy_rows(path: str) -> List[tuple]:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            return connection.execute(
                "SELECT doc_id, doc_name, chunk_id, chunk_index, chunk_text, source_meta, embedding "
                "FROM chunks ORDER BY doc_id, chunk_index"
            ).fetchall()
    except (sqlite3.Error, OSError) as exc:
        raise VectorStoreError("Could not read the legacy SQLite vector index") from exc


def _metadata_for_chunk(
    doc_id: str,
    doc_name: str,
    chunk: Mapping[str, Any],
    user_id: str | None,
    generation_id: str | None = None,
) -> Dict[str, Any]:
    source_meta = chunk.get("source_meta") or {}
    metadata: Dict[str, Any] = {
        "document_id": doc_id,
        "doc_name": doc_name or "uploaded",
        "chunk_index": int(chunk.get("chunk_index", 0)),
        "source_meta_json": json.dumps(source_meta, ensure_ascii=False),
    }
    if user_id is not None:
        metadata["user_id"] = str(user_id)
    if generation_id is not None:
        metadata["generation_id"] = generation_id
    page_number = source_meta.get("page_number")
    if isinstance(page_number, (int, float)) and not isinstance(page_number, bool):
        metadata["page_number"] = int(page_number)
    for key in ("topic_group", "section"):
        value = source_meta.get(key)
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
    return metadata


def _validated_embedding(value: Any) -> List[float]:
    if not isinstance(value, (list, tuple)) or not value:
        raise VectorStoreError("A document chunk is missing its embedding")
    try:
        embedding = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise VectorStoreError("A document chunk has an invalid embedding") from exc
    if any(not math.isfinite(item) for item in embedding):
        raise VectorStoreError("A document chunk has a non-finite embedding")
    return embedding


def _prepare_legacy_records(rows, owners):
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    embeddings: List[List[float]] = []
    for doc_id, doc_name, chunk_id, chunk_index, text, source_meta_json, _legacy_embedding in rows:
        try:
            source_meta = json.loads(source_meta_json or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise VectorStoreError("Legacy vector metadata contains invalid JSON") from exc
        if not isinstance(source_meta, dict):
            raise VectorStoreError("Legacy vector metadata is not an object")
        ids.append(str(chunk_id))
        documents.append(str(text or ""))
        metadatas.append(
            _metadata_for_chunk(
                str(doc_id),
                str(doc_name or "uploaded"),
                {"chunk_index": chunk_index, "source_meta": source_meta},
                owners.get(str(doc_id)) or source_meta.get("user_id"),
            )
        )

    for offset in range(0, len(documents), 128):
        batch = documents[offset:offset + 128]
        try:
            batch_embeddings = get_embeddings(batch)
        except Exception as exc:
            raise VectorStoreError(
                "Could not re-embed legacy chunks with all-MiniLM-L6-v2"
            ) from exc
        if len(batch_embeddings) != len(batch):
            raise VectorStoreError("Embedding service returned an unexpected number of legacy vectors")
        embeddings.extend(_validated_embedding(vector) for vector in batch_embeddings)
    if len({len(embedding) for embedding in embeddings}) > 1:
        raise VectorStoreError("Legacy chunks were embedded with inconsistent vector dimensions")
    return ids, documents, embeddings, metadatas


def _migrate_legacy_store_once(collection, persist_directory: str) -> None:
    legacy_path = os.getenv("LEGACY_VECTOR_STORE_PATH", _LEGACY_DB_PATH)
    marker_path = os.path.join(persist_directory, ".legacy-sqlite-migrated")
    if os.path.exists(marker_path) or not os.path.isfile(legacy_path):
        return

    rows = _read_legacy_rows(legacy_path)
    if not rows:
        with open(marker_path, "w", encoding="utf-8") as marker:
            marker.write("empty\n")
        return

    doc_ids = list(dict.fromkeys(str(row[0]) for row in rows if row[0]))
    owners = _lookup_legacy_owners(doc_ids)
    ids, documents, embeddings, metadatas = _prepare_legacy_records(rows, owners)

    for offset in range(0, len(ids), 500):
        end = offset + 500
        collection.upsert(
            ids=ids[offset:end],
            documents=documents[offset:end],
            embeddings=embeddings[offset:end],
            metadatas=metadatas[offset:end],
        )

    with open(marker_path, "w", encoding="utf-8") as marker:
        marker.write(f"migrated {len(ids)} chunks\n")
    logger.info("Migrated %d chunks from the legacy SQLite vector index", len(ids))


def migrate_legacy_sqlite_store(
    path: str,
    document_owners: Mapping[str, str] | None = None,
) -> int:
    """Import an existing SQLite vector index into the configured Chroma collection."""
    collection = _get_collection()
    rows = _read_legacy_rows(path)
    if not rows:
        return 0

    doc_ids = list(dict.fromkeys(str(row[0]) for row in rows if row[0]))
    owners = dict(document_owners or _lookup_legacy_owners(doc_ids))
    ids, documents, embeddings, metadatas = _prepare_legacy_records(rows, owners)

    for offset in range(0, len(ids), 500):
        end = offset + 500
        collection.upsert(
            ids=ids[offset:end],
            documents=documents[offset:end],
            embeddings=embeddings[offset:end],
            metadatas=metadatas[offset:end],
        )
    return len(ids)


def add_document_chunks(
    doc_id: str,
    doc_name: str,
    chunks: List[Dict[str, Any]],
    user_id: str | None = None,
) -> None:
    """Replace a document's chunk generation, retaining the old generation on failure."""
    if not chunks:
        raise VectorStoreError("Cannot index a document without chunks")
    ids = [str(chunk.get("chunk_id") or "") for chunk in chunks]
    if any(not chunk_id for chunk_id in ids) or len(ids) != len(set(ids)):
        raise VectorStoreError("Document chunks must have unique, non-empty IDs")

    embeddings = [_validated_embedding(chunk.get("embedding")) for chunk in chunks]
    if len({len(embedding) for embedding in embeddings}) != 1:
        raise VectorStoreError("Document chunk embeddings have inconsistent dimensions")

    collection_started = time.perf_counter()
    collection = _get_collection()
    logger.info("[ChromaDB] Collection lookup/initialization completed in %.3fs", time.perf_counter() - collection_started)
    where = _where_document(doc_id, user_id)
    lookup_started = time.perf_counter()
    previous = collection.get(where=where, include=["metadatas"])
    previous_ids = list(previous.get("ids") or [])
    logger.info("[ChromaDB] Existing chunk lookup completed in %.3fs (%d chunks)", time.perf_counter() - lookup_started, len(previous_ids))
    generation_id = uuid.uuid4().hex
    metadata = [
        _metadata_for_chunk(doc_id, doc_name, chunk, user_id, generation_id)
        for chunk in chunks
    ]

    try:
        upsert_started = time.perf_counter()
        collection.upsert(
            ids=ids,
            documents=[str(chunk.get("chunk_text") or "") for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadata,
        )
        stored = collection.get(ids=ids, include=["metadatas"])
        if set(stored.get("ids") or []) != set(ids):
            raise VectorStoreError("ChromaDB did not persist every document chunk")
        stale_ids = [chunk_id for chunk_id in previous_ids if chunk_id not in ids]
        if stale_ids:
            collection.delete(ids=stale_ids)
        logger.info("[ChromaDB] Upsert, verification, and stale cleanup completed in %.3fs (%d chunks)", time.perf_counter() - upsert_started, len(ids))
    except Exception as exc:
        new_ids = [chunk_id for chunk_id in ids if chunk_id not in previous_ids]
        if new_ids:
            collection.delete(ids=new_ids)
        if isinstance(exc, VectorStoreError):
            raise
        raise VectorStoreError("Could not replace the document's ChromaDB index") from exc


def get_document_chunks(doc_id: str, user_id: str | None = None) -> List[Dict[str, Any]]:
    collection = _get_collection()
    result = collection.get(
        where=_where_document(doc_id, user_id),
        include=["documents", "metadatas", "embeddings"],
    )
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    embeddings = result.get("embeddings")
    chunks = []
    for index, chunk_id in enumerate(ids):
        metadata = metadatas[index] or {}
        try:
            source_meta = json.loads(metadata.get("source_meta_json") or "{}")
        except json.JSONDecodeError as exc:
            raise VectorStoreError("Stored ChromaDB metadata is invalid") from exc
        chunk = {
            "chunk_id": chunk_id,
            "chunk_index": int(metadata.get("chunk_index", 0)),
            "chunk_text": documents[index] or "",
            "doc_name": metadata.get("doc_name", "uploaded"),
            "source_meta": source_meta,
            "embedding": embeddings[index].tolist() if hasattr(embeddings[index], "tolist") else list(embeddings[index]),
        }
        if metadata.get("user_id") is not None:
            chunk["user_id"] = metadata["user_id"]
        chunks.append(chunk)
    chunks.sort(key=lambda chunk: chunk["chunk_index"])
    return chunks


def similarity_search(
    doc_id: str,
    query_embedding: List[float],
    top_k: int = 8,
    min_score: float = 0.0,
    user_id: str | None = None,
) -> List[Tuple[float, Dict[str, Any]]]:
    if top_k <= 0:
        return []
    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return []
    result = collection.query(
        query_embeddings=[_validated_embedding(query_embedding)],
        n_results=min(top_k, count),
        where=_where_document(doc_id, user_id),
        include=["documents", "metadatas", "embeddings", "distances"],
    )
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    embeddings = (result.get("embeddings") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    matches = []
    for index, chunk_id in enumerate(ids):
        score = 1.0 - float(distances[index])
        if score < min_score:
            continue
        metadata = metadatas[index] or {}
        try:
            source_meta = json.loads(metadata.get("source_meta_json") or "{}")
        except json.JSONDecodeError as exc:
            raise VectorStoreError("Stored ChromaDB metadata is invalid") from exc
        embedding = embeddings[index]
        chunk = {
            "chunk_id": chunk_id,
            "chunk_index": int(metadata.get("chunk_index", 0)),
            "chunk_text": documents[index] or "",
            "doc_name": metadata.get("doc_name", "uploaded"),
            "source_meta": source_meta,
            "embedding": embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
        }
        if metadata.get("user_id") is not None:
            chunk["user_id"] = metadata["user_id"]
        matches.append((score, chunk))
    return matches


def delete_document_embeddings(doc_id: str, user_id: str | None = None) -> None:
    collection = _get_collection()
    collection.delete(where=_where_document(doc_id, user_id))
