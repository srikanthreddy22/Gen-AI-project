from datetime import timedelta

from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db
from app.models import Document, User
from app.services.rag_service import _doc_id_for_text
from auth_helpers import issue_auth_headers


def test_registration_login_profile_and_revocable_logout():
    app = create_app()
    client = app.test_client()

    missing_auth = client.post(
        "/api/upload/text/",
        json={"text": "A valid document string for the endpoint."},
    )
    assert missing_auth.status_code == 401

    registration = client.post(
        "/api/auth/register",
        json={"email": "Learner@Example.test", "username": "learner", "password": "secure-pass-123"},
    )
    assert registration.status_code == 201
    data = registration.get_json()
    assert data["user"]["email"] == "learner@example.test"
    token = data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    duplicate = client.post(
        "/api/auth/register",
        json={"email": "learner@example.test", "username": "another", "password": "secure-pass-123"},
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/api/auth/login",
        json={"email": "LEARNER@example.test", "password": "secure-pass-123"},
    )
    assert login.status_code == 200
    assert client.get("/api/auth/me", headers=headers).get_json()["username"] == "learner"

    profile = client.put(
        "/api/auth/profile",
        json={"full_name": "A Learner", "institution": "Example University"},
        headers=headers,
    )
    assert profile.status_code == 200
    assert client.get("/api/auth/me", headers=headers).get_json()["profile"]["full_name"] == "A Learner"

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200
    revoked = client.get("/api/auth/me", headers=headers)
    assert revoked.status_code == 401
    assert revoked.get_json()["error"] == "Access token has been revoked"


def test_cors_origin_value_is_sanitized_before_registration_requests():
    app = create_app({"CORS_ORIGINS": "CORS_ORIGINS=http://localhost:5173"})
    response = app.test_client().post(
        "/api/auth/register",
        json={"email": "cors@example.test", "username": "cors-user", "password": "secure-pass-123"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 201
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


def test_expired_access_token_returns_a_clear_unauthorized_response():
    app = create_app()
    with app.app_context():
        user = User(email="expired@example.test", username="expired", password_hash="hashed")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=user.id, expires_delta=timedelta(seconds=-1))

    response = app.test_client().get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Access token has expired"


def test_study_data_routes_require_a_valid_access_token():
    client = create_app().test_client()
    requests = [
        ("/api/upload/", {}),
        ("/api/upload/text/", {"text": "A document body long enough to index."}),
        ("/api/summarize/", {"text": "A short source sentence for summarization."}),
        ("/api/flashcards/", {"doc_id": "some-document"}),
        ("/api/quiz/", {"doc_id": "some-document"}),
        ("/api/export/pdf", {}),
    ]

    for path, payload in requests:
        response = client.post(path, json=payload)
        assert response.status_code == 401, path


def test_document_generation_routes_enforce_user_ownership():
    app = create_app()
    owner_headers, owner_id = issue_auth_headers(app, "document-owner")
    other_headers, other_user_id = issue_auth_headers(app, "other-learner")
    content = "A shared text body is isolated per account."
    owner_vector_id = _doc_id_for_text(content, owner_id)
    other_vector_id = _doc_id_for_text(content, other_user_id)
    assert owner_vector_id != other_vector_id

    with app.app_context():
        db.session.add_all([
            Document(
                vector_id=owner_vector_id,
                filename="owner.txt",
                original_name="owner.txt",
                user_id=owner_id,
            ),
            Document(
                vector_id=other_vector_id,
                filename="other.txt",
                original_name="other.txt",
                user_id=other_user_id,
            ),
        ])
        db.session.commit()

    client = app.test_client()
    for path in ("/api/flashcards/", "/api/quiz/"):
        response = client.post(
            path,
            json={"doc_id": owner_vector_id},
            headers=other_headers,
        )
        assert response.status_code == 404

    assert owner_headers["Authorization"] != other_headers["Authorization"]
