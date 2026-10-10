import os
import sys

TEST_ROOT = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_ROOT, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app
from app.routes import upload


def test_index_text_returns_document_id(monkeypatch):
    indexed = {}

    def fake_process_document(text, doc_name=None, force_reindex=False):
        indexed.update(text=text, doc_name=doc_name, force_reindex=force_reindex)
        return "doc-current"

    monkeypatch.setattr(upload, "process_document", fake_process_document)
    client = create_app().test_client()

    response = client.post(
        "/api/upload/text/",
        json={"text": "This is enough pasted text for document indexing.", "doc_name": "notes"},
    )

    assert response.status_code == 200
    assert response.get_json()["doc_id"] == "doc-current"
    assert response.get_json()["indexed"] is True
    assert indexed == {
        "text": "This is enough pasted text for document indexing.",
        "doc_name": "notes",
        "force_reindex": True,
    }


def test_index_text_rejects_empty_text():
    client = create_app().test_client()

    response = client.post("/api/upload/text/", json={"text": "  "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No text provided"
