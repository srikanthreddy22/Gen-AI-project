from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
import logging
from ..extensions import db
from ..models import Document, Flashcard
from ..services.generation_service import rag_generate_flashcards_from_doc
from ..services.vector_store import get_document_chunks
from ..services.flashcard_gen import _legacy_generate_flashcards
from ..services.persistence_service import get_owned_document, save_flashcards

bp = Blueprint("flashcards", __name__)
logger = logging.getLogger(__name__)


@bp.route("/flashcards/", methods=["POST"])
@jwt_required()
def flashcards_route():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    doc_id = doc_id.strip() if isinstance(doc_id, str) else ""
    count = min(int(data.get("count", 8)), 20)
    
    logger.info("[RAG] ════════════════════════════════════════════")
    logger.info("[RAG] Flashcard generation started")
    
    if not doc_id:
        logger.error("[RAG] ERROR: No document ID provided")
        return jsonify({"error": "No document ID provided. Please upload a document first."}), 400
    user_id = get_jwt_identity()
    if get_owned_document(doc_id, user_id) is None:
        return jsonify({"error": "Document not found"}), 404
    
    logger.info(f"[RAG] Document ID: {doc_id}")
    logger.info(f"[RAG] Requested count: {count}")
    
    try:
        generation_method = "rag+llm"
        try:
            cards = rag_generate_flashcards_from_doc(doc_id, count=count, user_id=user_id)
        except Exception as exc:
            logger.warning(f"[RAG] LLM flashcard generation failed: {exc}. Trying fallback extraction...", exc_info=True)
            chunks = get_document_chunks(doc_id, user_id=user_id)
            text = "\n\n".join(chunk.get("chunk_text", "") for chunk in chunks)
            cards = _legacy_generate_flashcards(text, count=count)
            generation_method = "local-fallback"

        try:
            save_flashcards(doc_id, cards, user_id)
        except LookupError:
            return jsonify({"error": "Document record not found"}), 404
        except Exception:
            logger.exception("[DB] Failed to persist generated flashcards")
            return jsonify({"error": "Flashcards could not be saved"}), 503

        logger.info(f"[RAG] ✓ Flashcard generation SUCCESS ({len(cards)} cards)")
        logger.info("[RAG] ════════════════════════════════════════════")
        
        return jsonify({
            "flashcards": cards,
            "count": len(cards),
            "doc_id": doc_id,
            "generation_method": generation_method,
            "success": True
        })
    except Exception as e:
        logger.error(f"[RAG] ✗ Flashcard generation FAILED: {str(e)}", exc_info=True)
        logger.info("[RAG] ════════════════════════════════════════════")
        return jsonify({
            "error": str(e),
            "generation_method": "error",
            "success": False
        }), 500


@bp.route("/flashcards/<string:card_id>/review", methods=["POST"])
@jwt_required()
def review_flashcard_route(card_id):
    user_id = get_jwt_identity()
    card = (
        Flashcard.query.join(Document)
        .filter(Flashcard.id == card_id, Document.user_id == user_id)
        .first()
    )
    if card is None:
        return jsonify({"error": "Flashcard not found"}), 404

    card.review_count += 1
    card.last_reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to persist flashcard review")
        return jsonify({"error": "Flashcard review could not be saved"}), 503

    return jsonify({
        "record_id": card.id,
        "review_count": card.review_count,
        "last_reviewed_at": card.last_reviewed_at.isoformat(),
    })
