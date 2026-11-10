from io import BytesIO

import fitz

from app import create_app
from app.models import Document
from app.routes.upload import _extract_document
from app.services import rag_service, vector_store
from auth_helpers import issue_auth_headers


def _pdf_bytes(pages):
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


def test_chunking_respects_sentence_boundaries_overlap_and_page_metadata(monkeypatch):
    sentences = [
        f"Sentence {index}: " + "important study content " * 7 + "ends here."
        for index in range(35)
    ]
    page_text = " ".join(sentences)
    chunks = rag_service._smart_chunk(
        page_text,
        chunk_size_chars=1000,
        overlap_chars=200,
        pages=[{"page_number": 4, "text": page_text}],
    )

    assert len(chunks) > 2
    assert all(len(chunk["chunk_text"]) <= 1000 for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk["source_meta"]["page_number"] == 4 for chunk in chunks)
    for previous, current in zip(chunks, chunks[1:]):
        overlap_length = max((
            length
            for length in range(1, min(len(previous["chunk_text"]), len(current["chunk_text"])) + 1)
            if previous["chunk_text"].endswith(current["chunk_text"][:length])
        ), default=0)
        assert overlap_length >= 150
        assert current["chunk_text"][:overlap_length].startswith("Sentence ")


def test_pdf_upload_indexes_page_numbers_and_persists_processing_status(monkeypatch, tmp_path):
    monkeypatch.setattr(
        rag_service,
        "get_embeddings",
        lambda texts, model=None: [[1.0, 0.0] for _ in texts],
    )
    pdf_content = _pdf_bytes([
        "Page one discusses document indexing and semantic retrieval.",
        "Page two explains how embeddings support retrieval.",
    ])
    pdf_path = tmp_path / "pages.pdf"
    pdf_path.write_bytes(pdf_content)
    text, error, pages = _extract_document(str(pdf_path), "pdf")
    assert not error
    assert "Page one" in text
    assert [page["page_number"] for page in pages] == [1, 2]

    app = create_app()
    headers, user_id = issue_auth_headers(app)
    response = app.test_client().post(
        "/api/upload/",
        data={"file": (BytesIO(pdf_content), "pages.pdf")},
        content_type="multipart/form-data",
        headers=headers,
    )

    assert response.status_code == 200
    doc_id = response.get_json()["doc_id"]
    chunks = vector_store.get_document_chunks(doc_id, user_id=user_id)
    assert chunks
    assert {chunk["source_meta"]["page_number"] for chunk in chunks} == {1, 2}
    with app.app_context():
        document = Document.query.filter_by(vector_id=doc_id).one()
        assert document.page_count == 2
        assert document.status == "indexed"
        assert document.is_indexed is True


def test_scanned_or_empty_pdf_is_rejected_and_failure_status_is_persisted():
    app = create_app()
    headers, user_id = issue_auth_headers(app)
    response = app.test_client().post(
        "/api/upload/",
        data={"file": (BytesIO(_pdf_bytes([""])), "scan.pdf")},
        content_type="multipart/form-data",
        headers=headers,
    )

    assert response.status_code == 400
    assert "no readable text" in response.get_json()["error"].casefold()
    with app.app_context():
        document = Document.query.filter_by(
            user_id=user_id,
            original_name="scan.pdf",
        ).one()
        assert document.status == "extraction_failed"
        assert document.vector_id is None
