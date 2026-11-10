from app import create_app
from app.extensions import db
from app.models import Document
from app.services import vector_store
from auth_helpers import issue_auth_headers


def test_document_deletion_enforces_owner_and_removes_chroma_vectors():
    app = create_app()
    owner_headers, owner_id = issue_auth_headers(app)
    other_headers, _ = issue_auth_headers(app)
    doc_id = "owned-document"

    with app.app_context():
        db.session.add(Document(
            vector_id=doc_id,
            filename="notes.txt",
            original_name="notes.txt",
            user_id=owner_id,
        ))
        db.session.commit()

    vector_store.add_document_chunks(
        doc_id,
        "notes.txt",
        [{
            "chunk_id": "owned-chunk",
            "chunk_index": 0,
            "chunk_text": "private content",
            "source_meta": {},
            "embedding": [1.0, 0.0],
        }],
        user_id=owner_id,
    )

    client = app.test_client()
    denied = client.delete(f"/api/documents/{doc_id}", headers=other_headers)
    assert denied.status_code == 404
    assert vector_store.get_document_chunks(doc_id, user_id=owner_id)

    deleted = client.delete(f"/api/documents/{doc_id}", headers=owner_headers)
    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": True, "doc_id": doc_id}
    assert vector_store.get_document_chunks(doc_id, user_id=owner_id) == []
    with app.app_context():
        assert Document.query.filter_by(vector_id=doc_id).first() is None
