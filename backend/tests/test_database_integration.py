import json

from app import create_app
from app.extensions import db
from app.models import (
    Conversation,
    Document,
    Message,
    Flashcard,
    Quiz,
    QuizAttempt,
    User,
)
from app.services.persistence_service import register_document
from auth_helpers import issue_auth_headers


def test_pasted_text_upload_creates_document_record(monkeypatch):
    from app.routes import upload

    monkeypatch.setattr(upload, "process_document", lambda *args, **kwargs: "vector-doc-1")
    app = create_app()
    headers, user_id = issue_auth_headers(app)
    response = app.test_client().post(
        "/api/upload/text/",
        json={"text": "Persist this document text in the relational database.", "doc_name": "notes"},
        headers=headers,
    )

    assert response.status_code == 200
    with app.app_context():
        document = Document.query.filter_by(vector_id="vector-doc-1").one()
        assert document.original_name == "notes"
        assert document.status == "indexed"
        assert document.is_indexed is True
        assert document.user_id == user_id
        assert document.content_hash


def test_generated_flashcards_and_quiz_questions_are_persisted(monkeypatch):
    from app.routes import flashcards, quiz

    app = create_app()
    headers, user_id = issue_auth_headers(app)
    with app.app_context():
        register_document("vector-doc-2", "study notes", "Document source text.", user_id=user_id)

    monkeypatch.setattr(
        flashcards,
        "rag_generate_flashcards_from_doc",
        lambda *args, **kwargs: [{
            "question": "What is persistence?",
            "answer": "Persistence stores data beyond a single request.",
            "topic": "Databases",
            "difficulty": "hard",
            "source_page": 3,
        }],
    )
    monkeypatch.setattr(
        quiz,
        "rag_generate_quiz_from_doc",
        lambda *args, **kwargs: {
            "questions": [{
                "question": "What does a primary key identify?",
                "options": ["A row", "A database", "A server", "A query"],
                "correct_answer": "A row",
                "explanation": "A primary key uniquely identifies a row.",
                "difficulty": "easy",
            }],
            "insufficient_material": False,
            "message": "Quiz generated successfully.",
        },
    )

    client = app.test_client()
    flashcard_response = client.post(
        "/api/flashcards/", json={"doc_id": "vector-doc-2", "count": 1}, headers=headers
    )
    quiz_response = client.post(
        "/api/quiz/", json={"doc_id": "vector-doc-2", "count": 1, "generation_id": "generation-1"},
        headers=headers,
    )
    repeated_response = client.post(
        "/api/flashcards/", json={"doc_id": "vector-doc-2", "count": 1}, headers=headers
    )

    assert flashcard_response.status_code == 200
    assert quiz_response.status_code == 200
    assert repeated_response.status_code == 200
    flashcard_id = flashcard_response.get_json()["flashcards"][0]["record_id"]
    assert repeated_response.get_json()["flashcards"][0]["record_id"] == flashcard_id
    quiz_question_id = quiz_response.get_json()["questions"][0]["record_id"]
    with app.app_context():
        document = Document.query.filter_by(vector_id="vector-doc-2").one()
        assert len(document.flashcards) == 1
        assert document.flashcards[0].topic == "Databases"
        assert document.flashcards[0].difficulty == "hard"
        assert document.flashcards[0].source_page == 3
        assert len(document.quizzes) == 1
        assert json.loads(document.quizzes[0].options)[0] == "A row"
        assert document.quizzes[0].quiz_id == "generation-1"

    review_response = client.post(
        f"/api/flashcards/{flashcard_id}/review", headers=headers
    )
    assert review_response.status_code == 200
    assert review_response.get_json()["review_count"] == 1
    with app.app_context():
        assert db.session.get(Flashcard, flashcard_id).review_count == 1

    other_user_headers, _ = issue_auth_headers(app)
    forbidden_review = client.post(
        f"/api/flashcards/{flashcard_id}/review", headers=other_user_headers
    )
    assert forbidden_review.status_code == 404

    correct_attempt = client.post(
        "/api/quiz/attempts",
        json={"question_id": quiz_question_id, "selected_answer": "A row"},
        headers=headers,
    )
    incorrect_attempt = client.post(
        "/api/quiz/attempts",
        json={"question_id": quiz_question_id, "selected_answer": "A database"},
        headers=headers,
    )
    assert correct_attempt.status_code == 201
    assert correct_attempt.get_json()["is_correct"] is True
    assert correct_attempt.get_json()["score"] == 1.0
    assert incorrect_attempt.status_code == 201
    assert incorrect_attempt.get_json()["is_correct"] is False
    history = client.get("/api/quiz/attempts?doc_id=vector-doc-2", headers=headers)
    assert history.status_code == 200
    assert len(history.get_json()["attempts"]) == 2
    assert {attempt["is_correct"] for attempt in history.get_json()["attempts"]} == {True, False}
    hidden_history = client.get("/api/quiz/attempts?doc_id=vector-doc-2", headers=other_user_headers)
    assert hidden_history.status_code == 200
    assert hidden_history.get_json()["attempts"] == []
    forbidden_attempt = client.post(
        "/api/quiz/attempts",
        json={"question_id": quiz_question_id, "selected_answer": "A row"},
        headers=other_user_headers,
    )
    assert forbidden_attempt.status_code == 404


def test_database_model_relationships_persist_as_a_connected_graph():
    app = create_app()
    with app.app_context():
        user = User(
            email="learner@example.test",
            username="learner",
            password_hash="hashed",
        )
        document = Document(
            vector_id="vector-doc-3",
            filename="lesson.pdf",
            original_name="lesson.pdf",
            user=user,
        )
        conversation = Conversation(
            user=user,
            document=document,
            title="Lesson questions",
        )
        conversation.messages.append(Message(role="user", content="Explain the lesson."))
        quiz_question = Quiz(
            document=document,
            question="What is the key idea?",
            options='["A", "B", "C", "D"]',
            correct_answer="A",
        )
        attempt = QuizAttempt(
            quiz=quiz_question,
            user=user,
            selected_answer="A",
            is_correct=True,
            score=1.0,
        )
        db.session.add_all([user, document, conversation, quiz_question, attempt])
        db.session.commit()

        assert document.user is user
        assert user.documents == [document]
        assert conversation.document is document
        assert conversation.messages[0].conversation is conversation
        assert quiz_question.document is document
        assert quiz_question.attempts[0] is attempt
        assert attempt.user is user
