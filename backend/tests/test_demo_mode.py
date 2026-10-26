import io
import os
import subprocess
import sys

import fitz

TEST_ROOT = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_ROOT, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app
from app.data.demo_flashcards import DEMO_FLASHCARDS
from app.data.demo_questions import DEMO_QUESTIONS
from app.routes import flashcards, quiz, upload


def _pdf_bytes(pages):
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


def _demo_client(monkeypatch):
    monkeypatch.setattr(upload, "demo_mode_enabled", lambda: True)
    monkeypatch.setattr(quiz, "demo_mode_enabled", lambda: True)
    monkeypatch.setattr(flashcards, "demo_mode_enabled", lambda: True)
    monkeypatch.setattr(
        upload,
        "process_document",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("RAG must not run in demo mode")),
    )
    return create_app().test_client()


def test_valid_pdf_returns_all_static_questions_and_flashcards_without_indexing(monkeypatch):
    client = _demo_client(monkeypatch)
    response = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(_pdf_bytes(["Readable demo PDF content."])), "notes.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["demo_mode"] is True
    assert data["indexed"] is True
    assert data["message"] == "PDF uploaded successfully. Demo study materials are ready!"
    assert len(data["questions"]) == 15
    assert len(data["flashcards"]) == 10
    assert [item["id"] for item in data["questions"]] == list(range(1, 16))
    for item, expected in zip(data["questions"], DEMO_QUESTIONS):
        correct = next(option[3:] for option in expected["options"] if option.startswith(f"{expected['correct_option']}. "))
        assert item["question"] == expected["question"]
        assert item["options"] == [option[3:] for option in expected["options"]]
        assert len(item["options"]) == 4
        assert item["correct"] == correct
        assert item["correct_answer"] == correct
        assert item["explanation"] == expected["explanation"]
    assert data["flashcards"] == DEMO_FLASHCARDS


def test_demo_upload_checks_only_a_small_readable_pdf_sample(monkeypatch):
    client = _demo_client(monkeypatch)
    response = client.post(
        "/api/upload/",
        data={
            "file": (
                io.BytesIO(_pdf_bytes(["First page has readable text."] * 3 + ["Later page content."] * 4)),
                "long-notes.pdf",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "First page has readable text." in response.get_json()["text"]
    assert "Later page content." not in response.get_json()["text"]


def test_demo_quiz_regeneration_rotates_questions_and_preserves_answers(monkeypatch):
    client = _demo_client(monkeypatch)
    upload_response = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(_pdf_bytes(["Readable PDF text."])), "notes.pdf")},
        content_type="multipart/form-data",
    )
    doc_id = upload_response.get_json()["doc_id"]

    response = client.post("/api/quiz/", json={"doc_id": doc_id, "count": 5})

    assert response.status_code == 200
    data = response.get_json()
    assert data["generation_method"] == "demo-static"
    assert data["count"] == 15
    assert [item["id"] for item in data["questions"]] == list(range(2, 16)) + [1]
    for item in data["questions"]:
        expected = DEMO_QUESTIONS[item["id"] - 1]
        correct = next(option[3:] for option in expected["options"] if option.startswith(f"{expected['correct_option']}. "))
        assert item["correct_answer"] == correct
        assert item["explanation"] == expected["explanation"]


def test_demo_flashcards_endpoint_returns_static_cards(monkeypatch):
    client = _demo_client(monkeypatch)
    upload_response = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(_pdf_bytes(["Readable PDF text."])), "notes.pdf")},
        content_type="multipart/form-data",
    )

    response = client.post("/api/flashcards/", json={"doc_id": upload_response.get_json()["doc_id"]})

    assert response.status_code == 200
    assert response.get_json()["flashcards"] == DEMO_FLASHCARDS
    assert response.get_json()["generation_method"] == "demo-static"


def test_demo_upload_rejects_corrupt_and_unreadable_pdfs(monkeypatch):
    client = _demo_client(monkeypatch)

    corrupt = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(b"%PDF-1.7 invalid"), "corrupt.pdf")},
        content_type="multipart/form-data",
    )
    scanned = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(_pdf_bytes([""])), "scanned.pdf")},
        content_type="multipart/form-data",
    )

    assert corrupt.status_code == 400
    assert "corrupted or unreadable" in corrupt.get_json()["error"]
    assert scanned.status_code == 400
    assert "no readable text" in scanned.get_json()["error"]


def test_demo_upload_rejects_password_protected_pdf(monkeypatch):
    client = _demo_client(monkeypatch)
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Protected document text.")
    protected = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="document-password",
    )
    document.close()

    response = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(protected), "protected.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "password-protected" in response.get_json()["error"]


def test_disabling_demo_mode_keeps_original_pdf_indexing_path(monkeypatch):
    monkeypatch.setattr(upload, "demo_mode_enabled", lambda: False)
    indexed = {}

    def fake_process_document(text, doc_name=None, force_reindex=False):
        indexed.update(text=text, doc_name=doc_name, force_reindex=force_reindex)
        return "doc-ai-mode"

    monkeypatch.setattr(upload, "process_document", fake_process_document)
    client = create_app().test_client()
    response = client.post(
        "/api/upload/",
        data={"file": (io.BytesIO(_pdf_bytes(["Original AI path remains enabled."])), "notes.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["doc_id"] == "doc-ai-mode"
    assert response.get_json()["indexed"] is True
    assert "demo_mode" not in response.get_json()
    assert indexed["doc_name"] == "notes.pdf"
    assert indexed["force_reindex"] is True


def test_demo_mode_startup_and_requests_do_not_import_ai_services():
    script = r"""
import io
import sys
import fitz
from app import create_app

document = fitz.open()
page = document.new_page()
page.insert_text((72, 72), "Readable PDF text for the demo.")
pdf = document.tobytes()
document.close()

client = create_app().test_client()
uploaded = client.post(
    "/api/upload/",
    data={"file": (io.BytesIO(pdf), "notes.pdf")},
    content_type="multipart/form-data",
)
assert uploaded.status_code == 200, uploaded.get_json()
doc_id = uploaded.get_json()["doc_id"]
assert client.post("/api/quiz/", json={"doc_id": doc_id}).status_code == 200
assert client.post("/api/flashcards/", json={"doc_id": doc_id}).status_code == 200
for module in (
    "app.services.generation_service",
    "app.services.openai_service",
    "app.services.rag_service",
    "app.services.vector_store",
    "openai",
    "transformers",
):
    assert module not in sys.modules, module
"""
    environment = os.environ.copy()
    environment["DEMO_MODE"] = "true"
    environment["PYTHONPATH"] = BACKEND_ROOT
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
