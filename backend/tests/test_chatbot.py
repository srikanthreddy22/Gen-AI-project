import json

from app import create_app
from app.extensions import db
from app.models import Conversation, Document
from app.services import chat_service, gemini_service, rag_service, vector_store
from auth_helpers import issue_auth_headers


def _create_document(app, user_id, doc_id="chat-document"):
    with app.app_context():
        db.session.add(Document(
            vector_id=doc_id,
            filename="chat.pdf",
            original_name="chat.pdf",
            user_id=user_id,
            page_count=2,
            status="indexed",
            is_indexed=True,
        ))
        db.session.commit()
    vector_store.add_document_chunks(
        doc_id,
        "chat.pdf",
        [{
            "chunk_id": f"{doc_id}-chunk",
            "chunk_index": 0,
            "chunk_text": "The document explains that semantic retrieval compares vector representations.",
            "source_meta": {"page_number": 2},
            "embedding": [1.0, 0.0],
        }],
        user_id=user_id,
    )
    return doc_id


def test_chatbot_persists_conversations_messages_history_and_page_citations(monkeypatch):
    app = create_app()
    headers, user_id = issue_auth_headers(app)
    doc_id = _create_document(app, user_id)
    monkeypatch.setattr(rag_service, "get_embeddings", lambda texts, model=None: [[1.0, 0.0] for _ in texts])
    model_messages = []

    def fake_chat_completion(messages, **kwargs):
        model_messages.append(messages)
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "answer": "Semantic retrieval compares vector representations.",
                        "citations": [2],
                    })
                }
            }]
        }

    monkeypatch.setattr(chat_service, "chat_completion", fake_chat_completion)
    client = app.test_client()
    created = client.post("/api/chat/conversations", json={"doc_id": doc_id}, headers=headers)
    assert created.status_code == 201
    conversation = created.get_json()["conversation"]
    assert conversation["doc_id"] == doc_id

    first = client.post(
        f"/api/chat/conversations/{conversation['id']}/messages",
        json={"message": "What does semantic retrieval compare?"},
        headers=headers,
    )
    assert first.status_code == 201
    assert first.get_json()["assistant_message"]["citations"] == [2]
    assert first.get_json()["sources"][0]["page_number"] == 2

    second = client.post(
        f"/api/chat/conversations/{conversation['id']}/messages",
        json={"message": "Can you restate that briefly?"},
        headers=headers,
    )
    assert second.status_code == 201
    assert any(
        item["role"] == "assistant"
        and item["content"] == "Semantic retrieval compares vector representations."
        for item in model_messages[1]
    )
    assert any(
        item["role"] == "user"
        and item["content"] == "What does semantic retrieval compare?"
        for item in model_messages[1]
    )

    history = client.get(
        f"/api/chat/conversations/{conversation['id']}/messages",
        headers=headers,
    )
    messages = history.get_json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1]["citations"] == [2]
    assert client.get("/api/chat/conversations", headers=headers).get_json()["conversations"][0]["id"] == conversation["id"]
    with app.app_context():
        assert Conversation.query.filter_by(id=conversation["id"], user_id=user_id).one()


def test_chatbot_hides_conversations_and_documents_from_other_users(monkeypatch):
    app = create_app()
    owner_headers, owner_id = issue_auth_headers(app)
    other_headers, _ = issue_auth_headers(app)
    doc_id = _create_document(app, owner_id, "private-chat-document")
    client = app.test_client()

    created = client.post(
        "/api/chat/conversations",
        json={"doc_id": doc_id},
        headers=owner_headers,
    )
    conversation_id = created.get_json()["conversation"]["id"]

    assert client.get(
        f"/api/chat/conversations/{conversation_id}/messages",
        headers=other_headers,
    ).status_code == 404
    assert client.post(
        "/api/chat/conversations",
        json={"doc_id": doc_id},
        headers=other_headers,
    ).status_code == 404
    assert client.get(
        "/api/chat/conversations",
        headers=other_headers,
    ).get_json()["conversations"] == []


def test_chatbot_rejects_unavailable_page_citations_without_persisting(monkeypatch):
    app = create_app()
    headers, user_id = issue_auth_headers(app)
    doc_id = _create_document(app, user_id, "citation-chat-document")
    monkeypatch.setattr(rag_service, "get_embeddings", lambda texts, model=None: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(
        chat_service,
        "chat_completion",
        lambda *args, **kwargs: {
            "choices": [{
                "message": {
                    "content": json.dumps({"answer": "Unsupported citation.", "citations": [99]})
                }
            }]
        },
    )
    client = app.test_client()
    conversation = client.post(
        "/api/chat/conversations",
        json={"doc_id": doc_id},
        headers=headers,
    ).get_json()["conversation"]

    response = client.post(
        f"/api/chat/conversations/{conversation['id']}/messages",
        json={"message": "Question"},
        headers=headers,
    )
    assert response.status_code == 502
    history = client.get(
        f"/api/chat/conversations/{conversation['id']}/messages",
        headers=headers,
    )
    assert history.get_json()["messages"] == []


def test_chatbot_falls_back_to_local_rag_when_gemini_unavailable(monkeypatch):
    app = create_app()
    headers, user_id = issue_auth_headers(app)
    doc_id = _create_document(app, user_id, "fallback-chat-document")
    monkeypatch.setattr(rag_service, "get_embeddings", lambda texts, model=None: [[1.0, 0.0] for _ in texts])

    def failing_chat_completion(*args, **kwargs):
        raise gemini_service.GeminiQuotaError("Gemini quota exhausted")

    monkeypatch.setattr(chat_service, "chat_completion", failing_chat_completion)
    client = app.test_client()
    conversation = client.post(
        "/api/chat/conversations",
        json={"doc_id": doc_id},
        headers=headers,
    ).get_json()["conversation"]

    response = client.post(
        f"/api/chat/conversations/{conversation['id']}/messages",
        json={"message": "What is semantic retrieval?"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.get_json()
    assert "semantic retrieval" in data["assistant_message"]["content"].lower()
    assert 2 in data["assistant_message"]["citations"]
    assert len(data["sources"]) > 0
    assert data["sources"][0]["page_number"] == 2

