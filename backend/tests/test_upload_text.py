import os
import sys

TEST_ROOT = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_ROOT, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app
from app.routes import upload
from auth_helpers import issue_auth_headers


def test_index_text_returns_document_id(monkeypatch):
    indexed = {}

    def fake_process_document(text, doc_name=None, force_reindex=False, owner_id=None):
        indexed.update(text=text, doc_name=doc_name, force_reindex=force_reindex)
        return "doc-current"

    monkeypatch.setattr(upload, "process_document", fake_process_document)
    app = create_app()
    headers, user_id = issue_auth_headers(app)
    client = app.test_client()

    response = client.post(
        "/api/upload/text/",
        json={"text": "This is enough pasted text for document indexing.", "doc_name": "notes"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["doc_id"] == "doc-current"
    assert response.get_json()["indexed"] is True
    assert indexed == {
        "text": "This is enough pasted text for document indexing.",
        "doc_name": "notes",
        "force_reindex": True,
    }
    from app.models import Document

    with app.app_context():
        document = Document.query.filter_by(vector_id="doc-current").one()
        assert document.user_id == user_id


def test_index_text_rejects_empty_text():
    app = create_app()
    headers, _ = issue_auth_headers(app)
    client = app.test_client()

    response = client.post("/api/upload/text/", json={"text": "  "}, headers=headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "No text provided"
