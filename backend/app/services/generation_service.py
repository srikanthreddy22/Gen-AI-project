import os
import json
import logging
import random
from typing import List, Dict, Any, Optional
from .rag_service import process_document, retrieve_relevant
from .openai_service import chat_completion
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
        sections.append(f"--- [PASSAGE {i}: {sec}] ---\n{txt}")
    return "\n\n".join(sections)


def _get_diverse_chunks(doc_id: str, query: str, top_k: int = 8, chunk_offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieve diverse chunks across different topic groups in the document."""
    all_chunks = get_document_chunks(doc_id)
    if not all_chunks:
        return []
    
    # If document has few chunks, return all of them
    if len(all_chunks) <= top_k:
        return all_chunks

    # Group chunks by topic_group if available
    grouped = {}
    for c in all_chunks:
        meta = c.get("source_meta") or {}
        grp = meta.get("topic_group") or "default"
        grouped.setdefault(grp, []).append(c)

    # Pick representative chunks across groups with offset rotation
    selected = []
    groups = list(grouped.values())
    random.seed(chunk_offset)
    
    # Round-robin selection
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

    # If still need more chunks, supplement with similarity search
    if len(selected) < top_k:
        sim_chunks = retrieve_relevant(doc_id, query, top_k=top_k)
        for sc in sim_chunks:
            if sc not in selected:
                selected.append(sc)
            if len(selected) >= top_k:
                break

    return selected[:top_k]


def rag_generate_flashcards_from_doc(doc_id: str, count: int = 8) -> List[Dict[str, Any]]:
    """Generate high-quality, concept-driven study flashcards from an indexed document."""
    logger.info(f"[RAG] Flashcard generation started with doc_id={doc_id}, count={count}")
    
    existing_chunks = get_document_chunks(doc_id)
    if not existing_chunks:
        raise ValueError(f"Document {doc_id} not found in index. Please upload and index first.")
    
    # Retrieve diverse candidate chunks covering the core content
    chunks = _get_diverse_chunks(
        doc_id, 
        query="fundamental concepts, core definitions, mechanisms, processes, principles, and key facts",
        top_k=min(len(existing_chunks), max(DEFAULT_TOP_K, count))
    )
    
    context = _build_context(chunks)
    logger.info(f"[RAG] Built context from {len(chunks)} chunks ({len(context)} chars)")
    
    system_prompt = (
        "You are an expert university-level study designer specializing in high-yield exam preparation. "
        "Your job is to transform the supplied document passages into concise, accurate, concept-driven learning materials. "
        "Every fact must be supported by the provided context; do not invent details, examples, or broader claims. "
        "Return ONLY valid JSON with a top-level 'flashcards' list."
    )
    
    user_prompt = f"""Generate {count} university-style study flashcards from the document passages below.

DOCUMENT CONTEXT:
{context}

FLASHCARD QUALITY CRITERIA:
1. FRONT (Question):
   - Must be a polished, standalone exam question that tests a significant concept, mechanism, definition, comparison, or effect.
   - Prefer high-value question types such as: "What is [Concept]?", "How does [Process] work?", "Why does [Outcome] occur?", "How does [A] differ from [B]?", "What is the primary function of [X]?"
   - Avoid vague, generic, or fragmentary prompts such as "What is this?", "What about data?", or broad questions lacking a clear concept.
2. BACK (Answer):
   - Must give a precise, academically appropriate answer supported directly by the source text.
   - Keep each answer to 1-3 clear sentences and self-contained enough that a student can revise without re-reading the whole passage.
   - Do not return incomplete clauses, paraphrases that distort the meaning, or unsupported speculation.
3. CONTENT COVERAGE:
   - Cover definitions, core ideas, cause-effect relationships, comparisons, mechanisms, and applications when explicitly supported by the text.
   - Each card should cover a distinct concept; avoid duplication or near-identical cards on the same fact.
   - Remove headers, page numbers, references, and irrelevant formatting artifacts.
4. GROUNDING:
   - Use only the supplied document. If a concept is not in the passage, do not generate it.
   - Prefer accurate, clearly-written questions over forcing quantity.

JSON SCHEMA:
{{
  "flashcards": [
    {{
      "id": 1,
      "question": "What is machine learning?",
      "answer": "Machine learning is a branch of artificial intelligence that enables computers to learn patterns from data and improve performance without being explicitly programmed for every task.",
      "type": "definition",
      "topic": "Machine Learning"
    }}
  ]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    resp = chat_completion(messages, temperature=0.2, max_tokens=2000, response_format={"type": "json_object"})
    text_out = resp["choices"][0]["message"]["content"]
    
    parsed = {}
    try:
        parsed = json.loads(text_out)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if m:
            parsed = json.loads(m.group(0))

    cards = validate_flashcards(parsed, count=count)
    logger.info(f"[RAG] Flashcards validated: {len(cards)} cards generated")
    
    if len(cards) < count:
        logger.warning(f"[RAG] Generated {len(cards)}/{count} cards. Trying fallback cards to satisfy count...")
        # Supplement with fallback from chunk text if necessary
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
    generation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate multiple-choice quiz questions from document context, excluding previously asked questions."""
    logger.info(f"[RAG] Quiz generation started with doc_id={doc_id}, count={count}, exclusions={len(exclude_questions or [])}")
    
    existing_chunks = get_document_chunks(doc_id)
    if not existing_chunks:
        raise ValueError(f"Document {doc_id} not found in index. Please upload and index first.")
        
    exclusions = exclude_questions or []
    
    # Calculate offset based on number of exclusions to cycle through chunks across quiz generations
    chunk_offset = (len(exclusions) // count) * 2
    chunks = _get_diverse_chunks(
        doc_id,
        query="important concepts, examination questions, mechanisms, comparisons, and key facts",
        top_k=min(len(existing_chunks), max(DEFAULT_TOP_K, count)),
        chunk_offset=chunk_offset
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
        "You are an expert university assessment designer creating high-quality exam questions from a supplied study document. "
        "Generate only questions that are directly supported by the source passages. Keep the wording academically precise, "
        "concept-focused, and varied across definitions, mechanisms, comparisons, and causal relationships. "
        "Never invent facts, use fill-in-the-blank stems, or create questions that copy a sentence fragment from the document. "
        "CRITICAL: each question must have its own distinct, context-specific distractor set. Never reuse the same three incorrect options across different questions; every incorrect option should be tailored to its specific question and semantically different. "
        "Return ONLY valid JSON with a top-level 'questions' list."
    )

    user_prompt = f"""Generate up to {count} university-level multiple-choice exam questions from the provided document passages.

DOCUMENT CONTEXT:
{context}
{exclusion_text}

QUESTION DESIGN REQUIREMENTS:
1. Choose meaningful, exam-relevant concepts, definitions, relationships, mechanisms, comparisons, causes, or consequences that are explicitly supported by the passages.
2. Use polished, natural question stems. Strong forms include: "What is [concept]?", "Which statement best describes [concept]?", "How does [process] work?", "Why does [effect] occur?", and "How does [A] differ from [B]?"
3. Never create fill-in-the-blank questions, sentence fragments, or questions that simply repeat a passage verbatim.
4. The correct answer must be explicitly supported by the document and must match one option exactly.
6. Provide exactly 4 plausible answer choices whenever the passage supports enough high-quality distractors. If not enough unique distractors exist, skip the question instead of reusing generic filler options.
7. Ensure there is exactly one defensible correct answer. Distractors should be contextually relevant to that question, clearly wrong or less complete, and not reused from other questions.
7. Explanation should be brief but academically grounded: 1 to 2 sentences that directly connect the answer to the document evidence.
8. Difficulty should be 'easy', 'medium', or 'hard' depending on conceptual complexity.
9. Exclude page numbers, headers, footers, or isolated fragments. Prefer fewer strong questions over weak or unsupported ones.
11. For each question, independently generate three distinct plausible wrong answers that are designed for that question only. Never use a shared distractor pool across the entire quiz.
10. If the document contains only a few distinct ideas, generate fewer than the maximum; do not force low-quality questions.

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

    # Use temperature 0.4 to ensure varied question generation across retries
    resp = chat_completion(messages, temperature=0.4, max_tokens=2200, response_format={"type": "json_object"})
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
    
    # If duplicates were rejected and we didn't get enough questions, retry once with targeted prompt
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
                temperature=0.5,
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
