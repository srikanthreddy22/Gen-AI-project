import hashlib
import json
import logging
import re
import uuid

from ..extensions import db
from ..models import Document, Flashcard, Quiz
from .validation_service import is_similar_question

logger = logging.getLogger(__name__)


def register_document(
    vector_id,
    original_name,
    content,
    file_size=0,
    storage_path=None,
    page_count=0,
    status="indexed",
    user_id=None,
):
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    document = Document.query.filter_by(vector_id=vector_id).first() if vector_id else None
    if document is None:
        document = Document(
            vector_id=vector_id,
            filename=original_name,
            original_name=original_name,
            user_id=user_id,
        )
        db.session.add(document)
    elif document.user_id not in (None, user_id):
        raise PermissionError("Document belongs to another user")

    if user_id is not None:
        document.user_id = user_id
    document.filename = original_name
    document.original_name = original_name
    document.file_size = file_size
    if storage_path is not None:
        document.storage_path = storage_path
    document.content_hash = content_hash
    document.page_count = page_count
    document.status = status
    document.is_indexed = status == "indexed"
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if vector_id:
            existing = Document.query.filter_by(vector_id=vector_id).first()
            if existing:
                return existing
        raise
    return document


def get_document_by_vector_id(vector_id):
    return Document.query.filter_by(vector_id=vector_id).first()


def get_owned_document(vector_id, user_id):
    return Document.query.filter_by(vector_id=vector_id, user_id=user_id).first()


def get_owned_quiz_questions(vector_id, user_id):
    document = get_owned_document(vector_id, user_id)
    if document is None:
        return None
    return [question.question for question in document.quizzes]


def get_stored_quiz_questions(vector_id, user_id, limit=None):
    document = get_owned_document(vector_id, user_id)
    if document is None:
        return []
    quizzes = list(document.quizzes)
    if not quizzes:
        return []
    results = []
    for q in quizzes:
        opts = []
        try:
            if isinstance(q.options, str):
                opts = json.loads(q.options)
            elif isinstance(q.options, list):
                opts = q.options
        except Exception:
            opts = []
        results.append({
            "id": q.id,
            "record_id": q.id,
            "question": q.question,
            "options": opts,
            "correct": q.correct_answer,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation or f"Correct answer: {q.correct_answer}",
            "difficulty": q.difficulty or "medium",
            "source_page": q.source_page,
            "topic": getattr(q, "topic", "") or "General",
        })
    return results[:limit] if limit and limit > 0 else results


def _normalized_question(question):
    return re.sub(r"\W+", " ", (question or "").casefold()).strip()


def save_flashcards(vector_id, cards, user_id):
    document = get_owned_document(vector_id, user_id)
    if document is None:
        raise LookupError("Document record not found")

    existing_cards = list(document.flashcards)
    saved = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        question = str(card.get("question") or "").strip()
        answer = str(card.get("answer") or "").strip()
        normalized = _normalized_question(question)
        if not normalized or not answer:
            continue

        duplicate = next(
            (
                existing_card for existing_card in existing_cards
                if is_similar_question(question, existing_card.question, threshold=0.65)
            ),
            None,
        )
        if duplicate is not None:
            card["record_id"] = duplicate.id
            continue

        source_page = card.get("source_page")
        if not isinstance(source_page, int) or isinstance(source_page, bool) or source_page <= 0:
            source_page = None
        saved_card = Flashcard(
            question=question,
            answer=answer,
            card_type=str(card.get("type") or card.get("card_type") or "concept")[:50],
            topic=str(card.get("topic") or "")[:255],
            difficulty=str(card.get("difficulty") or "medium")[:20],
            source_page=source_page,
        )
        document.flashcards.append(saved_card)
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
            raise
        card["record_id"] = saved_card.id
        existing_cards.append(saved_card)
        saved += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return saved


def save_quiz_questions(vector_id, questions, user_id, quiz_id=None):
    document = get_owned_document(vector_id, user_id)
    if document is None:
        raise LookupError("Document record not found")

    existing_questions = list(document.quizzes)
    saved = 0
    for item in questions:
        if not isinstance(item, dict):
            continue
        question_text = str(item.get("question") or "").strip()
        normalized = _normalized_question(question_text)
        if not normalized:
            continue
        duplicate = next(
            (
                existing_question for existing_question in existing_questions
                if _normalized_question(existing_question.question) == normalized
            ),
            None,
        )
        if duplicate is not None:
            item["record_id"] = duplicate.id
            continue
        options = item.get("options") or []
        correct_answer = item.get("correct_answer") or item.get("correct") or ""
        if not isinstance(options, (list, dict)) or not correct_answer:
            logger.warning("Skipping malformed generated quiz question for document %s", vector_id)
            continue
        saved_question = Quiz(
            quiz_id=quiz_id or str(uuid.uuid4()),
            question=question_text,
            options=json.dumps(options),
            correct_answer=str(correct_answer)[:255],
            explanation=str(item.get("explanation") or ""),
            difficulty=str(item.get("difficulty") or "medium")[:20],
            source_page=item.get("source_page"),
        )
        document.quizzes.append(saved_question)
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
            raise
        item["record_id"] = saved_question.id
        existing_questions.append(saved_question)
        saved += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return saved
