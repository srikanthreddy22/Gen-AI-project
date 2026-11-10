import random
import uuid
import logging
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from ..extensions import db
from ..models import Document, Quiz, QuizAttempt
from ..services.generation_service import rag_generate_quiz_from_doc
from ..services.vector_store import get_document_chunks
from ..services.quiz_gen import _generate_quiz_locally
from ..services.persistence_service import get_owned_quiz_questions, get_stored_quiz_questions, save_quiz_questions

bp = Blueprint("quiz", __name__)
logger = logging.getLogger(__name__)


@bp.route("/quiz/", methods=["GET"])
@jwt_required()
def get_quiz_route():
    doc_id = request.args.get("doc_id", "").strip()
    if not doc_id:
        return jsonify({"error": "No document ID provided"}), 400
    user_id = get_jwt_identity()
    stored = get_stored_quiz_questions(doc_id, user_id)
    return jsonify({
        "questions": stored,
        "count": len(stored),
        "doc_id": doc_id,
        "success": True,
    })


@bp.route("/quiz/", methods=["POST"])
@jwt_required()
def quiz_route():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    doc_id = doc_id.strip() if isinstance(doc_id, str) else ""
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
    user_id = get_jwt_identity()

    # Check if document exists for this user
    server_history = get_owned_quiz_questions(doc_id, user_id)
    if server_history is None:
        return jsonify({"error": "Document not found"}), 404

    # If the user did not specify any exclusions (e.g. initial request or reopening document),
    # check if we already have stored questions in the database
    if not clean_exclusions:
        stored_questions = get_stored_quiz_questions(doc_id, user_id, limit=count)
        if stored_questions and len(stored_questions) >= count:
            logger.info(f"[RAG] Returning {len(stored_questions)} existing stored quiz questions for doc_id={doc_id}")
            return jsonify({
                "questions": stored_questions,
                "count": len(stored_questions),
                "doc_id": doc_id,
                "generation_id": generation_id,
                "generation_method": "db-cache",
                "insufficient_material": False,
                "message": "Quiz loaded successfully from your document notes.",
                "success": True,
            })

    # When user sends exclusions, combine them
    combined_exclusions = list(dict.fromkeys(clean_exclusions + (server_history if clean_exclusions else [])))
    logger.info(f"[RAG] Total combined exclusions: {len(combined_exclusions)}")
    
    try:
        generation_method = "rag+llm"
        try:
            res = rag_generate_quiz_from_doc(
                doc_id, 
                count=count, 
                exclude_questions=combined_exclusions, 
                generation_id=generation_id,
                user_id=user_id,
            )
            questions = res["questions"]
            insufficient = res.get("insufficient_material", False)
            message = res.get("message", "Quiz generated successfully.")
        except Exception as exc:
            logger.warning(
                "[RAG] Gemini quiz generation failed (%s). Trying local generator...",
                type(exc).__name__,
            )
            chunks = get_document_chunks(doc_id, user_id=user_id)
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
            chunks = get_document_chunks(doc_id, user_id=user_id)
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

        # Persist any newly generated questions
        if questions:
            try:
                save_quiz_questions(doc_id, questions, user_id, quiz_id=generation_id)
            except LookupError:
                return jsonify({"error": "Document record not found"}), 404
            except Exception:
                logger.exception("[DB] Failed to persist generated quiz questions")

        # If questions count is less than requested, supplement from document's stored questions
        if len(questions) < count:
            stored = get_stored_quiz_questions(doc_id, user_id)
            clean_norm = set(q.strip().casefold() for q in clean_exclusions)
            curr_norm = set((q.get("question") or "").strip().casefold() for q in questions)
            for sq in stored:
                sq_norm = (sq.get("question") or "").strip().casefold()
                if sq_norm not in clean_norm and sq_norm not in curr_norm:
                    questions.append(sq)
                    if len(questions) >= count:
                        break

        # If still empty (all concepts already seen in exclusions), provide a review set
        if not questions:
            stored = get_stored_quiz_questions(doc_id, user_id)
            if stored:
                shuffled = list(stored)
                random.shuffle(shuffled)
                questions = shuffled[:count]
                message = "All key concepts have been covered! Here is a review quiz from your notes."
                insufficient = False

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


@bp.route("/quiz/attempts", methods=["POST"])
@jwt_required()
def submit_quiz_attempt_route():
    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    selected_answer = data.get("selected_answer")
    if not isinstance(question_id, str) or not question_id.strip():
        return jsonify({"error": "A quiz question ID is required"}), 400
    if not isinstance(selected_answer, str) or not selected_answer.strip():
        return jsonify({"error": "A selected answer is required"}), 400

    user_id = get_jwt_identity()
    quiz_question = (
        Quiz.query.join(Document)
        .filter(Quiz.id == question_id, Document.user_id == user_id)
        .first()
    )
    if quiz_question is None:
        return jsonify({"error": "Quiz question not found"}), 404

    try:
        options = json.loads(quiz_question.options)
    except (TypeError, json.JSONDecodeError):
        logger.exception("Stored quiz options are invalid for question %s", question_id)
        return jsonify({"error": "Quiz question data is invalid"}), 503
    if not isinstance(options, list) or selected_answer not in options:
        return jsonify({"error": "Selected answer is not one of the question options"}), 400

    is_correct = selected_answer == quiz_question.correct_answer
    attempt = QuizAttempt(
        quiz=quiz_question,
        user_id=user_id,
        selected_answer=selected_answer,
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
    )
    db.session.add(attempt)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to persist quiz attempt")
        return jsonify({"error": "Quiz attempt could not be saved"}), 503

    return jsonify({
        "id": attempt.id,
        "question_id": quiz_question.id,
        "quiz_id": quiz_question.quiz_id,
        "question": quiz_question.question,
        "selected_answer": attempt.selected_answer,
        "correct_answer": quiz_question.correct_answer,
        "is_correct": attempt.is_correct,
        "score": attempt.score,
        "explanation": quiz_question.explanation,
        "source_page": quiz_question.source_page,
        "created_at": attempt.created_at.isoformat(),
    }), 201


@bp.route("/quiz/attempts", methods=["GET"])
@jwt_required()
def get_quiz_attempts_route():
    user_id = get_jwt_identity()
    attempts_query = (
        QuizAttempt.query.join(Quiz).join(Document)
        .filter(QuizAttempt.user_id == user_id, Document.user_id == user_id)
    )
    doc_id = request.args.get("doc_id")
    if doc_id:
        attempts_query = attempts_query.filter(Document.vector_id == doc_id)
    attempts = attempts_query.order_by(QuizAttempt.created_at.desc()).limit(100).all()

    return jsonify({
        "attempts": [{
            "id": attempt.id,
            "question_id": attempt.quiz.id,
            "quiz_id": attempt.quiz.quiz_id,
            "question": attempt.quiz.question,
            "selected_answer": attempt.selected_answer,
            "correct_answer": attempt.quiz.correct_answer,
            "is_correct": attempt.is_correct,
            "score": attempt.score,
            "explanation": attempt.quiz.explanation,
            "source_page": attempt.quiz.source_page,
            "created_at": attempt.created_at.isoformat(),
        } for attempt in attempts]
    })
