import uuid
import logging
from flask import Blueprint, request, jsonify
from ..demo_mode import demo_mode_enabled

bp = Blueprint("quiz", __name__)
logger = logging.getLogger(__name__)

# In-memory session tracking of previously generated questions per document
DOC_QUIZ_HISTORY = {}


@bp.route("/quiz/", methods=["POST"])
def quiz_route():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id", "").strip()
    count = min(int(data.get("count", 5)), 15)
    
    # Receive exclusions from frontend and create a unique generation id
    req_exclusions = data.get("exclude_questions") or []
    generation_id = data.get("generation_id") or f"gen_{uuid.uuid4().hex[:8]}"
    
    # Extract string question texts if dicts were sent
    clean_exclusions = []
    for item in req_exclusions:
        if isinstance(item, str):
            clean_exclusions.append(item.strip())
        elif isinstance(item, dict) and "question" in item:
            clean_exclusions.append(str(item["question"]).strip())

    logger.info("[RAG] ============================================")
    logger.info(f"[RAG] Quiz generation started - gen_id={generation_id}, doc_id={doc_id}, count={count}")
    logger.info(f"[RAG] Request exclusions count: {len(clean_exclusions)}")
    
    if not doc_id:
        logger.error("[RAG] ERROR: No document ID provided")
        return jsonify({"error": "No document ID provided. Please upload a document first."}), 400

    if demo_mode_enabled():
        from ..services.demo_service import has_document, materials_for_document

        if not has_document(doc_id):
            return jsonify({"error": "Demo document not found. Please upload the PDF again."}), 404
        materials = materials_for_document(doc_id, regenerate=True)
        questions = materials["questions"]
        return jsonify({
            "questions": questions,
            "count": len(questions),
            "doc_id": doc_id,
            "generation_id": generation_id,
            "generation_method": "demo-static",
            "insufficient_material": False,
            "message": "The predefined demo questions have been reordered.",
            "success": True,
        })

    # Combine with server-side document history
    server_history = DOC_QUIZ_HISTORY.setdefault(doc_id, set())
    combined_exclusions = list(set(clean_exclusions).union(server_history))
    logger.info(f"[RAG] Total combined exclusions: {len(combined_exclusions)}")
    
    try:
        from ..services.generation_service import rag_generate_quiz_from_doc
        from ..services.openai_service import is_insufficient_quota
        from ..services.vector_store import get_document_chunks
        from ..services.quiz_gen import _generate_quiz_locally

        generation_method = "rag+llm"
        try:
            res = rag_generate_quiz_from_doc(
                doc_id, 
                count=count, 
                exclude_questions=combined_exclusions, 
                generation_id=generation_id
            )
            questions = res["questions"]
            insufficient = res.get("insufficient_material", False)
            message = res.get("message", "Quiz generated successfully.")
        except Exception as exc:
            if not is_insufficient_quota(exc):
                logger.warning(f"[RAG] LLM quiz generation failed: {exc}. Trying local generator...")
            chunks = get_document_chunks(doc_id)
            text = "\n\n".join(chunk.get("chunk_text", "") for chunk in chunks)
            questions = _generate_quiz_locally(
                text,
                count=count,
                exclude_questions=combined_exclusions,
            )
            generation_method = "local-fallback"
            insufficient = len(questions) < count
            message = (
                f"Generated {len(questions)} grounded question(s); the document does not contain "
                "enough distinct concept statements for more reliable questions."
                if insufficient and questions
                else "This document does not contain enough clear concept statements to create reliable quiz questions. "
                "Try a longer document with definitions or explanations."
                if insufficient
                else "Generated using the local, source-grounded question generator."
            )

        if not questions and generation_method != "local-fallback":
            chunks = get_document_chunks(doc_id)
            text = "\n\n".join(chunk.get("chunk_text", "") for chunk in chunks)
            questions = _generate_quiz_locally(
                text,
                count=count,
                exclude_questions=combined_exclusions,
            )
            generation_method = "local-fallback"
            insufficient = len(questions) < count
            message = (
                f"Generated {len(questions)} grounded question(s); the document does not contain "
                "enough distinct concept statements for more reliable questions."
                if insufficient and questions
                else "This document does not contain enough clear concept statements to create reliable quiz questions. "
                "Try a longer document with definitions or explanations."
                if insufficient
                else "Generated using the local, source-grounded question generator."
            )

        # Register generated questions in server-side history
        for q in questions:
            q_text = q.get("question", "").strip()
            if q_text:
                server_history.add(q_text)

        logger.info(f"[RAG] [OK] Quiz generation SUCCESS ({len(questions)} questions)")
        logger.info("[RAG] ============================================")
        
        return jsonify({
            "questions": questions, 
            "count": len(questions),
            "doc_id": doc_id,
            "generation_id": generation_id,
            "generation_method": generation_method,
            "insufficient_material": insufficient,
            "message": message,
            "success": True
        })
    except Exception as e:
        logger.error(f"[RAG] [FAIL] Quiz generation FAILED: {str(e)}", exc_info=True)
        logger.info("[RAG] ============================================")
        return jsonify({
            "error": str(e),
            "generation_method": "error",
            "success": False
        }), 500
