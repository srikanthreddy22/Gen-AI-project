import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import select

from ..extensions import db
from ..models import Conversation, Document, Message
from ..services.chat_service import ChatResponseError, answer_document_question
from ..services.gemini_service import GeminiServiceError
from ..services.persistence_service import get_owned_document

bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)


def _serialize_message(message):
    try:
        citations = json.loads(message.citations or "[]")
    except json.JSONDecodeError:
        logger.exception("Stored citations are invalid for message %s", message.id)
        citations = []
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "citations": citations,
        "created_at": message.created_at.isoformat(),
    }


def _serialize_conversation(conversation):
    document = conversation.document
    return {
        "id": conversation.id,
        "title": conversation.title,
        "doc_id": document.vector_id if document else None,
        "document_name": document.original_name if document else None,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _get_owned_conversation(conversation_id, user_id):
    return Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()


@bp.route("/chat/conversations", methods=["GET"])
@jwt_required()
def list_conversations():
    user_id = get_jwt_identity()
    query = Conversation.query.filter_by(user_id=user_id)
    doc_id = request.args.get("doc_id")
    if doc_id:
        document = get_owned_document(doc_id, user_id)
        if document is None:
            return jsonify({"error": "Document not found"}), 404
        query = query.filter_by(document_id=document.id)
    conversations = query.order_by(Conversation.updated_at.desc()).all()
    return jsonify({"conversations": [_serialize_conversation(item) for item in conversations]})


@bp.route("/chat/conversations", methods=["POST"])
@jwt_required()
def create_conversation():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        return jsonify({"error": "A document ID is required"}), 400

    user_id = get_jwt_identity()
    document = get_owned_document(doc_id.strip(), user_id)
    if document is None:
        return jsonify({"error": "Document not found"}), 404

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "New conversation"
    conversation = Conversation(
        user_id=user_id,
        document_id=document.id,
        title=title.strip()[:255],
    )
    db.session.add(conversation)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Could not create conversation for document %s", doc_id)
        return jsonify({"error": "Conversation could not be created"}), 503
    return jsonify({"conversation": _serialize_conversation(conversation)}), 201


@bp.route("/chat/conversations/<string:conversation_id>/messages", methods=["GET"])
@jwt_required()
def get_conversation_messages(conversation_id):
    user_id = get_jwt_identity()
    conversation = _get_owned_conversation(conversation_id, user_id)
    if conversation is None:
        return jsonify({"error": "Conversation not found"}), 404
    if conversation.document is None or conversation.document.user_id != user_id:
        return jsonify({"error": "Conversation not found"}), 404

    messages = db.session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
    ).scalars().all()
    return jsonify({
        "conversation": _serialize_conversation(conversation),
        "messages": [_serialize_message(message) for message in messages],
    })


@bp.route("/chat/conversations/<string:conversation_id>/messages", methods=["POST"])
@jwt_required()
def send_message(conversation_id):
    data = request.get_json(silent=True) or {}
    question = data.get("message")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "A message is required"}), 400
    question = question.strip()
    if len(question) > 5000:
        return jsonify({"error": "Message must be 5000 characters or fewer"}), 413

    user_id = get_jwt_identity()
    conversation = _get_owned_conversation(conversation_id, user_id)
    if conversation is None or conversation.document is None:
        return jsonify({"error": "Conversation not found"}), 404
    document = Document.query.filter_by(
        id=conversation.document_id,
        user_id=user_id,
    ).first()
    if document is None or not document.vector_id:
        return jsonify({"error": "Conversation not found"}), 404

    prior_messages = db.session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
    ).scalars().all()
    history = [
        {"role": message.role, "content": message.content}
        for message in prior_messages
        if message.role in {"user", "assistant"}
    ]

    try:
        result = answer_document_question(
            document.vector_id,
            user_id,
            question,
            history=history,
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 422
    except GeminiServiceError:
        logger.exception("Gemini failed to answer a chatbot question")
        return jsonify({"error": "The assistant is temporarily unavailable"}), 502
    except ChatResponseError:
        logger.exception("Gemini returned an invalid chatbot response")
        return jsonify({"error": "The assistant returned an invalid response"}), 502
    except Exception:
        logger.exception("Could not generate an answer for conversation %s", conversation_id)
        return jsonify({"error": "The question could not be answered"}), 500

    message_time = datetime.utcnow()
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=question,
        citations="[]",
        created_at=message_time,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        citations=json.dumps(result["citations"]),
        created_at=message_time + timedelta(microseconds=1),
    )
    db.session.add_all([user_message, assistant_message])
    if conversation.title == "New conversation":
        conversation.title = question[:255]
    conversation.updated_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Could not persist chatbot messages for conversation %s", conversation_id)
        return jsonify({"error": "The response could not be saved"}), 503

    return jsonify({
        "user_message": _serialize_message(user_message),
        "assistant_message": _serialize_message(assistant_message),
        "sources": result["sources"],
    }), 201
