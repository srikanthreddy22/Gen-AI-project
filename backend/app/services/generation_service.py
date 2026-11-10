import os
import json
import logging
import random
from typing import List, Dict, Any, Optional
from .rag_service import process_document, retrieve_relevant
from .gemini_service import chat_completion
from .validation_service import validate_flashcards, validate_quiz, is_similar_question
from .vector_store import get_document_chunks

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "8"))


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    """Build formatted context string from retrieved chunks."""
    sections = []
    for i, c in enumerate(chunks, 1):
        txt = (c.get("chunk_text") or "").strip()
        meta = c.get("source_meta") or {}
        sec = meta.get("section") or f"Section {i}"
        page = meta.get("page_number")
        page_label = f", PAGE {page}" if isinstance(page, int) and page > 0 else ""
        sections.append(f"--- [PASSAGE {i}: {sec}{page_label}] ---\n{txt}")
    return "\n\n".join(sections)


def _get_diverse_chunks(
    doc_id: str,
    query: str,
    top_k: int = 8,
    chunk_offset: int = 0,
    user_id: str | None = None,
) -> List[Dict[str, Any]]:
    """Retrieve diverse chunks across different topic groups in the document."""
    all_chunks = get_document_chunks(doc_id, user_id=user_id)
    if not all_chunks:
        return []
    
    if len(all_chunks) <= top_k:
        return all_chunks

    grouped = {}
    for c in all_chunks:
        meta = c.get("source_meta") or {}
        grp = meta.get("topic_group") or "default"
        grouped.setdefault(grp, []).append(c)

    selected = []
    groups = list(grouped.values())
    random.seed(chunk_offset)
    
    max_len = max(len(g) for g in groups)
    for step in range(max_len):
        for g in groups:
            idx = (step + chunk_offset) % len(g)
            chunk = g[idx]
            if chunk not in selected:
                selected.append(chunk)
            if len(selected) >= top_k:
                break
        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        sim_chunks = retrieve_relevant(doc_id, query, top_k=top_k, user_id=user_id)
        for sc in sim_chunks:
            if sc not in selected:
                selected.append(sc)
            if len(selected) >= top_k:
                break

    return selected[:top_k]


def rag_generate_flashcards_from_doc(
    doc_id: str,
    count: int = 8,
    user_id: str | None = None,
) -> List[Dict[str, Any]]:
    """Generate high-quality, concept-driven study flashcards from an indexed document."""
    logger.info(f"[RAG] Flashcard generation started with doc_id={doc_id}, count={count}")
    
    existing_chunks = get_document_chunks(doc_id, user_id=user_id)
    if not existing_chunks:
        raise ValueError(f"Document {doc_id} not found in index. Please upload and index first.")
    
    chunks = _get_diverse_chunks(
        doc_id, 
        query="fundamental concepts, core definitions, mechanisms, processes, principles, SQL commands, and key facts",
        top_k=min(len(existing_chunks), max(DEFAULT_TOP_K, count)),
        user_id=user_id,
    )
    
    context = _build_context(chunks)
    logger.info(f"[RAG] Built context from {len(chunks)} chunks ({len(context)} chars)")
    
    system_prompt = (
        "You are an expert university professor and technical curriculum designer. "
        "Your task is to transform technical and academic source passages into exceptionally clear, "
        "concept-driven flashcards for high-yield mastery. "
        "Every fact must be strictly grounded in the supplied context.\n\n"
        "QUALITY GUIDELINES:\n"
        "1. First, identify the central concepts, definitions, architectural principles, and SQL/code statements in the text.\n"
        "2. Formulate polished, complete, standalone questions testing deep conceptual understanding (e.g., 'What is the purpose of the DROP INDEX statement in SQL?').\n"
        "3. Strictly avoid fragmentary prompts, incomplete sentences, or copying raw syntax tags (never generate 'What is the key idea of ○ Example...').\n"
        "4. Answers must be 1 to 3 informative, grammatically correct sentences directly supported by the context.\n"
        "Return ONLY valid JSON matching the schema with a top-level 'flashcards' list."
    )
    
    user_prompt = f"""Generate {count} university-style study flashcards from the document passages below.

DOCUMENT CONTEXT:
{context}

FLASHCARD QUALITY CRITERIA:
1. FRONT (Question):
   - Must be a polished, standalone exam question that tests a significant concept, mechanism, definition, comparison, command, or effect.
   - Good examples: "What is [Concept]?", "What is the purpose of the [Command] statement in SQL?", "How does [Process] work?", "Why does [Outcome] occur?", "How does [A] differ from [B]?"
   - Never copy bullet characters (○, ●, ■, •), unparsed code fragments, or incomplete clauses into questions.
2. BACK (Answer):
   - Give a precise, complete answer supported directly by the source text.
   - 1-3 clear sentences that explain the concept self-containedly.
3. TOPIC & DIFFICULTY:
   - Provide a concise topic (e.g. "Database Indexing", "SQL Constraints") and classify difficulty as "easy", "medium", or "hard".
   - Include source_page only when the passage includes an exact page number.

JSON SCHEMA:
{{
  "flashcards": [
    {{
      "id": 1,
      "question": "What is the primary function of database indexing?",
      "answer": "Database indexing creates auxiliary data structures that accelerate data retrieval operations on specific table columns without scanning every row.",
      "type": "concept",
      "topic": "Database Indexing",
      "difficulty": "medium",
      "source_page": 1
    }}
  ]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    resp = chat_completion(messages, temperature=0.2, max_tokens=2200, response_format={"type": "json_object"})
    text_out = resp["choices"][0]["message"]["content"]
    
    parsed = {}
    try:
        parsed = json.loads(text_out)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if m:
            parsed = json.loads(m.group(0))

    valid_pages = {
        meta["page_number"]
        for chunk in chunks
        for meta in [chunk.get("source_meta") or {}]
        if isinstance(meta.get("page_number"), int) and meta["page_number"] > 0
    }
    cards = validate_flashcards(parsed, count=count, valid_pages=valid_pages)
    logger.info(f"[RAG] Flashcards validated: {len(cards)} cards generated")
    
    # If fewer than count cards were accepted, retry with a supplemental prompt
    if len(cards) < count and len(existing_chunks) > 1:
        needed = count - len(cards)
        logger.info(f"[RAG] Attempting supplemental generation for {needed} remaining flashcards...")
        seen_qs = "\n".join(f"- {c['question']}" for c in cards)
        supp_prompt = f"""Generate {needed} additional, completely different study flashcards from the document passages below.
DO NOT REPEAT OR TEST THE SAME CONCEPTS AS THESE EXISTING CARDS:
{seen_qs}

DOCUMENT CONTEXT:
{context}

Return valid JSON with top-level 'flashcards' matching the schema."""
        try:
            supp_resp = chat_completion(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": supp_prompt}],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            supp_text = supp_resp["choices"][0]["message"]["content"]
            supp_parsed = json.loads(supp_text)
            supp_cards = validate_flashcards(supp_parsed, count=needed, valid_pages=valid_pages)
            for sc in supp_cards:
                if not any(is_similar_question(sc["question"], c["question"]) for c in cards):
                    sc["id"] = len(cards) + 1
                    cards.append(sc)
                if len(cards) >= count:
                    break
        except Exception as supp_err:
            logger.warning(f"[RAG] Supplemental flashcard generation failed: {supp_err}")

    # Fallback only if count still not reached
    if len(cards) < count:
        logger.warning(f"[RAG] Generated {len(cards)}/{count} cards. Supplementing with offline fallback...")
        all_text = "\n\n".join(c.get("chunk_text", "") for c in existing_chunks)
        from .flashcard_gen import _legacy_generate_flashcards
        fallback_cards = _legacy_generate_flashcards(all_text, count=count)
        for fc in fallback_cards:
            if not any(is_similar_question(fc["question"], c["question"]) for c in cards):
                fc["id"] = len(cards) + 1
                cards.append(fc)
            if len(cards) >= count:
                break

    return cards[:count]


def rag_generate_quiz_from_doc(
    doc_id: str,
    count: int = 5,
    exclude_questions: Optional[List[str]] = None,
    generation_id: Optional[str] = None,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Generate multiple-choice quiz questions from document context, excluding previously asked questions."""
    logger.info(f"[RAG] Quiz generation started with doc_id={doc_id}, count={count}, exclusions={len(exclude_questions or [])}")
    
    existing_chunks = get_document_chunks(doc_id, user_id=user_id)
    if not existing_chunks:
        raise ValueError(f"Document {doc_id} not found in index. Please upload and index first.")
        
    exclusions = exclude_questions or []
    chunk_offset = (len(exclusions) // count) * 2
    chunks = _get_diverse_chunks(
        doc_id,
        query="important concepts, examination questions, mechanisms, comparisons, SQL commands, and key facts",
        top_k=min(len(existing_chunks), max(DEFAULT_TOP_K, count)),
        chunk_offset=chunk_offset,
        user_id=user_id,
    )
    
    context = _build_context(chunks)
    logger.info(f"[RAG] Built context from {len(chunks)} chunks ({len(context)} chars) with offset={chunk_offset}")
    
    exclusion_text = ""
    if exclusions:
        exclusion_list = "\n".join(f"- {q}" for q in exclusions[-15:])
        exclusion_text = (
            f"\nPREVIOUSLY ASKED QUESTIONS (DO NOT REPEAT, REPHRASE, OR TEST THE SAME FACTS):\n"
            f"{exclusion_list}\n\n"
            f"CRITICAL INSTRUCTION: You must generate {count} COMPLETELY NEW questions that test DIFFERENT concepts, "
            f"details, mechanisms, or definitions from the provided passages."
        )

    system_prompt = (
        "You are an expert university assessment designer creating high-quality, rigorous multiple-choice exam questions "
        "from supplied technical study documents.\n\n"
        "QUESTION REQUIREMENTS:\n"
        "1. Ground all questions directly in the source text.\n"
        "2. Include conceptual, application-based, and scenario-based questions with precise wording.\n"
        "3. Never create fill-in-the-blank questions, sentence fragments, or questions containing bullet symbols.\n"
        "4. Each question must have exactly 4 choices with exactly one unambiguously correct answer.\n"
        "5. Distractors must be plausible, contextually relevant to that specific question, and not generic filler.\n"
        "6. Provide a concise, clear explanation (1-2 sentences) directly linking the answer to document evidence.\n"
        "Return ONLY valid JSON with a top-level 'questions' list matching the schema."
    )

    user_prompt = f"""Generate up to {count} university-level multiple-choice exam questions from the provided document passages.

DOCUMENT CONTEXT:
{context}
{exclusion_text}

QUESTION DESIGN REQUIREMENTS:
1. Choose meaningful concepts, definitions, SQL statements, rules, mechanisms, comparisons, causes, or consequences.
2. Formulate clear, polished question stems: e.g., "What is the purpose of [command]?", "Which statement best describes [concept]?", "In a database schema with high read traffic, what is the consequence of [action]?"
3. Exactly 4 choices per question: 1 correct answer and 3 distinct, plausible distractors tailored to that question.
4. Correct answer must match one option exactly.
5. Provide a 1-2 sentence explanation grounded in the text.
6. Set difficulty to 'easy', 'medium', or 'hard'.

JSON SCHEMA:
{{
  "questions": [
    {{
      "id": 1,
      "question": "What is the primary function of transformers in NLP?",
      "options": [
        "Sequential processing using recurrent loops",
        "Parallel self-attention across token sequences",
        "Converting speech waveforms to text",
        "Rule-based grammatical parsing"
      ],
      "correct": "Parallel self-attention across token sequences",
      "explanation": "Transformers utilize self-attention mechanisms to process all tokens in parallel without sequential recurrent dependencies.",
      "difficulty": "medium",
      "topic": "Transformers"
    }}
  ]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    resp = chat_completion(messages, temperature=0.3, max_tokens=2200, response_format={"type": "json_object"})
    text_out = resp["choices"][0]["message"]["content"]
    
    parsed = {}
    try:
        parsed = json.loads(text_out)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if m:
            parsed = json.loads(m.group(0))

    questions = validate_quiz(parsed, exclude_questions=exclusions, count=count, source_text=context)
    logger.info(f"[RAG] Quiz questions validated: {len(questions)}/{count} questions accepted (exclusions filtered)")
    
    # Supplemental retry if needed
    if len(questions) < count and len(existing_chunks) > 1:
        needed = count - len(questions)
        logger.info(f"[RAG] Attempting supplemental generation for {needed} remaining questions...")
        
        all_exclusions = exclusions + [q["question"] for q in questions]
        supp_exclusion_list = "\n".join(f"- {q}" for q in all_exclusions[-20:])
        
        supp_prompt = f"""Generate {needed} brand-new, unique multiple-choice questions from the following text.
DO NOT REPEAT OR REPHRASE ANY OF THESE PREVIOUS QUESTIONS:
{supp_exclusion_list}

CONTEXT:
{context}

Return valid JSON with top-level 'questions' matching the schema."""

        try:
            supp_resp = chat_completion(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": supp_prompt}],
                temperature=0.4,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            supp_text = supp_resp["choices"][0]["message"]["content"]
            supp_parsed = json.loads(supp_text)
            supp_questions = validate_quiz(
                supp_parsed,
                exclude_questions=all_exclusions,
                count=needed,
                source_text=context,
            )
            for sq in supp_questions:
                sq["id"] = len(questions) + 1
                questions.append(sq)
                if len(questions) >= count:
                    break
        except Exception as supp_err:
            logger.warning(f"[RAG] Supplemental question generation failed: {supp_err}")

    insufficient_material = len(questions) < count
    
    return {
        "questions": questions,
        "count": len(questions),
        "insufficient_material": insufficient_material,
        "message": (
            "The document content has been thoroughly covered. All available non-duplicate questions have been generated."
            if insufficient_material else "New quiz questions generated successfully."
        )
    }


def rag_generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    doc_id = process_document(text)
    return rag_generate_flashcards_from_doc(doc_id, count=count)


def rag_generate_quiz(text: str, count: int = 5) -> List[Dict[str, Any]]:
    doc_id = process_document(text)
    res = rag_generate_quiz_from_doc(doc_id, count=count)
    return res["questions"]
