import json
import os
import sqlite3

import pytest

from app.services import vector_store


def _chunk(chunk_id, index, text, embedding, page_number=None):
    source_meta = {"page_number": page_number} if page_number else {}
    return {
        "chunk_id": chunk_id,
        "chunk_index": index,
        "chunk_text": text,
        "source_meta": source_meta,
        "embedding": embedding,
    }


def test_chroma_storage_filters_by_document_and_user_and_deletes_scoped_data():
    vector_store.add_document_chunks(
        "document-a",
        "A",
        [_chunk("a-1", 0, "alpha", [1.0, 0.0], page_number=2)],
        user_id="user-a",
    )
    vector_store.add_document_chunks(
        "document-a",
        "A",
        [_chunk("b-1", 0, "beta", [0.0, 1.0])],
        user_id="user-b",
    )
    vector_store.add_document_chunks(
        "document-b",
        "B",
        [_chunk("a-2", 0, "other document", [0.8, 0.2])],
        user_id="user-a",
    )

    user_a_chunks = vector_store.get_document_chunks("document-a", user_id="user-a")
    assert len(user_a_chunks) == 1
    assert user_a_chunks[0]["chunk_text"] == "alpha"
    assert user_a_chunks[0]["source_meta"]["page_number"] == 2
    assert user_a_chunks[0]["user_id"] == "user-a"
    assert vector_store.get_document_chunks("document-a", user_id="unknown") == []
    assert vector_store.get_document_chunks("missing", user_id="user-a") == []

    results = vector_store.similarity_search(
        "document-a",
        [1.0, 0.0],
        top_k=5,
        user_id="user-a",
    )
    assert len(results) == 1
    assert results[0][1]["chunk_text"] == "alpha"
    assert results[0][0] == pytest.approx(1.0)

    vector_store.delete_document_embeddings("document-a", user_id="user-a")
    assert vector_store.get_document_chunks("document-a", user_id="user-a") == []
    assert [chunk["chunk_text"] for chunk in vector_store.get_document_chunks("document-a", user_id="user-b")] == ["beta"]
    assert [chunk["chunk_text"] for chunk in vector_store.get_document_chunks("document-b", user_id="user-a")] == ["other document"]


def test_reindex_replaces_chunks_without_duplicates_and_persists():
    vector_store.add_document_chunks(
        "document",
        "Original",
        [_chunk("old-1", 0, "old content", [1.0, 0.0])],
        user_id="owner",
    )

    vector_store.add_document_chunks(
        "document",
        "Updated",
        [
            _chunk("new-1", 0, "new first chunk", [0.0, 1.0]),
            _chunk("new-2", 1, "new second chunk", [1.0, 1.0]),
        ],
        user_id="owner",
    )
    chunks = vector_store.get_document_chunks("document", user_id="owner")
    assert [chunk["chunk_id"] for chunk in chunks] == ["new-1", "new-2"]

    persist_directory = os.path.abspath(os.environ["CHROMA_PERSIST_DIRECTORY"])
    vector_store._clients.pop(persist_directory, None)
    persisted = vector_store.get_document_chunks("document", user_id="owner")
    assert [chunk["chunk_text"] for chunk in persisted] == ["new first chunk", "new second chunk"]


def test_failed_chroma_upsert_keeps_the_previous_generation(monkeypatch):
    vector_store.add_document_chunks(
        "document",
        "Original",
        [_chunk("old", 0, "old content", [1.0, 0.0])],
        user_id="owner",
    )
    collection = vector_store._get_collection()

    class FailingCollection:
        def __getattr__(self, name):
            return getattr(collection, name)

        def upsert(self, **kwargs):
            raise RuntimeError("simulated Chroma write failure")

    monkeypatch.setattr(vector_store, "_get_collection", lambda: FailingCollection())
    with pytest.raises(vector_store.VectorStoreError, match="replace the document"):
        vector_store.add_document_chunks(
            "document",
            "Updated",
            [_chunk("new", 0, "new content", [0.0, 1.0])],
            user_id="owner",
        )
    assert [chunk["chunk_id"] for chunk in vector_store.get_document_chunks("document", user_id="owner")] == ["old"]


def test_legacy_sqlite_import_preserves_metadata_and_reembeds_idempotently(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store, "get_embeddings", lambda texts: [[0.6, 0.8] for _ in texts])
    legacy_path = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_path) as connection:
        connection.execute(
            "CREATE TABLE chunks (doc_id TEXT, doc_name TEXT, chunk_id TEXT PRIMARY KEY, "
            "chunk_index INTEGER, chunk_text TEXT, source_meta TEXT, embedding TEXT)"
        )
        connection.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-document",
                "legacy.pdf",
                "legacy-chunk",
                0,
                "legacy content",
                json.dumps({"page_number": 3, "section": "Intro"}),
                json.dumps([1.0, 0.0]),
            ),
        )

    assert vector_store.migrate_legacy_sqlite_store(
        str(legacy_path),
        document_owners={"legacy-document": "legacy-owner"},
    ) == 1
    assert vector_store.migrate_legacy_sqlite_store(
        str(legacy_path),
        document_owners={"legacy-document": "legacy-owner"},
    ) == 1

    chunks = vector_store.get_document_chunks("legacy-document", user_id="legacy-owner")
    assert len(chunks) == 1
    assert chunks[0]["chunk_text"] == "legacy content"
    assert chunks[0]["source_meta"] == {"page_number": 3, "section": "Intro"}
    assert chunks[0]["doc_name"] == "legacy.pdf"
    assert chunks[0]["embedding"] == pytest.approx([0.6, 0.8])
    assert vector_store.get_document_chunks("legacy-document", user_id="other-owner") == []
