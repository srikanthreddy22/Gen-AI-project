from flask import Blueprint, request, jsonify
import logging
from ..services.generation_service import rag_generate_quiz_from_doc
from ..services.openai_service import is_insufficient_quota
from ..services.vector_store import get_document_chunks
from ..services.quiz_gen import _generate_quiz_locally

bp = Blueprint("quiz", __name__)
logger = logging.getLogger(__name__)

@bp.route("/quiz/", methods=["POST"])
def quiz_route():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id", "").strip()
    count = min(int(data.get("count", 5)), 15)
    
    logger.info("[RAG] ════════════════════════════════════════════")
    logger.info("[RAG] Quiz generation started")
    
    if not doc_id:
        logger.error("[RAG] ERROR: No document ID provided")
        return jsonify({"error": "No document ID provided. Please upload a document first."}), 400
    
    logger.info(f"[RAG] Document ID: {doc_id}")
    logger.info(f"[RAG] Requested count: {count}")
    
    try:
        generation_method = "rag+openai"
        try:
            questions = rag_generate_quiz_from_doc(doc_id, count=count)
        except Exception as exc:
            if not is_insufficient_quota(exc):
                raise
            logger.warning("[RAG] OpenAI quota exhausted; using local quiz generation")
            chunks = get_document_chunks(doc_id)
            text = "\n\n".join(chunk.get("chunk_text", "") for chunk in chunks)
            questions = _generate_quiz_locally(text, count=count)
            generation_method = "local-fallback"
        logger.info(f"[RAG] ✓ Quiz generation SUCCESS")
        logger.info(f"[RAG] Generated {len(questions)} quiz questions")
        logger.info("[RAG] ════════════════════════════════════════════")
        
        return jsonify({
            "questions": questions, 
            "count": len(questions),
            "doc_id": doc_id,
            "generation_method": generation_method,
            "success": True
        })
    except Exception as e:
        logger.error(f"[RAG] ✗ Quiz generation FAILED: {str(e)}", exc_info=True)
        logger.info("[RAG] ════════════════════════════════════════════")
        return jsonify({
            "error": str(e),
            "generation_method": "error",
            "success": False
        }), 500
