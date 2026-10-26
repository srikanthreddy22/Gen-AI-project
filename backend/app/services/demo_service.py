"""Fast static study materials for presentation mode, independent of PDF content."""

import threading
import uuid

from ..data.demo_flashcards import DEMO_FLASHCARDS
from ..data.demo_questions import DEMO_QUESTIONS

_documents: dict[str, int] = {}
_documents_lock = threading.Lock()


def register_document() -> tuple[str, dict]:
    """Register a validated upload and return the first fixed study set."""
    doc_id = f"demo_{uuid.uuid4().hex}"
    with _documents_lock:
        _documents[doc_id] = 0
    return doc_id, materials_for_document(doc_id)


def has_document(doc_id: str) -> bool:
    with _documents_lock:
        return doc_id in _documents


def materials_for_document(doc_id: str, regenerate: bool = False) -> dict:
    with _documents_lock:
        if doc_id not in _documents:
            raise KeyError(doc_id)
        if regenerate:
            _documents[doc_id] = (_documents[doc_id] + 1) % len(DEMO_QUESTIONS)
        offset = _documents[doc_id]

    ordered = DEMO_QUESTIONS[offset:] + DEMO_QUESTIONS[:offset]
    questions = []
    for item in ordered:
        options = [option[3:] for option in item["options"]]
        correct = next(option[3:] for option in item["options"] if option.startswith(f"{item['correct_option']}. "))
        questions.append({
            "id": item["id"],
            "question": item["question"],
            "options": options,
            "correct": correct,
            "correct_answer": correct,
            "explanation": item["explanation"],
            "difficulty": "medium",
            "topic": "Machine Learning",
        })
    return {
        "questions": questions,
        "flashcards": [dict(card) for card in DEMO_FLASHCARDS],
        "summary": {
            "bullets": [{
                "text": "Demo study materials use a fixed machine-learning question and flashcard set; they are not generated from the uploaded PDF.",
                "tag": "concept",
            }],
            "keywords": ["Machine Learning", "Neural Networks", "Classification", "Regression"],
            "stats": {"input_words": 0, "bullet_count": 1, "compression_pct": 0, "model": "demo-static"},
        },
    }
