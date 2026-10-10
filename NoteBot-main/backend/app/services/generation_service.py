from typing import List, Dict, Any
from .rag_service import process_document, retrieve_relevant
from .openai_service import chat_completion, get_embeddings
from .validation_service import validate_flashcards, validate_quiz
from .vector_store import get_document_chunks
import os
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "8"))


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    b = []
    for c in chunks:
        b.append(f"[source_id:{c.get('chunk_id')} score:{c.get('score'):.3f}]\n{c.get('chunk_text')}\n")
    return "\n---\n".join(b)


def rag_generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    doc_id = process_document(text)
    prompt = f"Generate up to {count} high-quality educational flashcards from the supplied context. Return strict JSON with top-level key 'flashcards' as a list. Each card must have question, answer, source_chunk_ids (list), and optional topic. Do not hallucinate; only use the provided context."
    # retrieve diverse chunks
    chunks = retrieve_relevant(doc_id, "flashcards generation", top_k=DEFAULT_TOP_K, min_score=0.05)
    context = _build_context(chunks)
    system = "You are an educational content generation assistant. Use only the provided context to create flashcards. Return only valid JSON matching the schema."
    user = f"CONTEXT:\n{context}\n\nINSTRUCTIONS:\n{prompt}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    resp = chat_completion(messages, temperature=0.0, max_tokens=1500)
    text_out = resp["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(text_out)
    except Exception:
        # try to extract JSON substring
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if not m:
            raise
        parsed = json.loads(m.group(0))

    cards = validate_flashcards(parsed)
    return cards[:count]


def rag_generate_quiz(text: str, count: int = 5) -> List[Dict[str, Any]]:
    doc_id = process_document(text)
    prompt = f"Generate {count} multiple-choice questions (exactly 4 options each) from the supplied context. Return strict JSON with top-level key 'questions'. Each question must include question, options (4 unique strings), correct_answer, explanation (optional), source_chunk_ids (list), and topic. Use only the provided context. If you cannot produce enough valid questions, produce fewer."
    chunks = retrieve_relevant(doc_id, "quiz generation", top_k=DEFAULT_TOP_K, min_score=0.05)
    context = _build_context(chunks)
    system = "You are an educational MCQ generation assistant. Use only the provided context to create questions. Return only valid JSON matching the schema."
    user = f"CONTEXT:\n{context}\n\nINSTRUCTIONS:\n{prompt}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    resp = chat_completion(messages, temperature=0.0, max_tokens=1500)
    text_out = resp["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(text_out)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if not m:
            raise
        parsed = json.loads(m.group(0))

    questions = validate_quiz(parsed)
    return questions[:count]


def rag_generate_flashcards_from_doc(doc_id: str, count: int = 8) -> List[Dict[str, Any]]:
    """Generate flashcards using an already-indexed document ID."""
    logger.info(f"[RAG] Flashcard generation started with doc_id={doc_id}")
    
    # Verify document exists in index
    existing_chunks = get_document_chunks(doc_id)
    if not existing_chunks:
        raise ValueError(f"Document {doc_id} not found in index. Please upload and index first.")
    
    logger.info(f"[RAG] Document {doc_id} has {len(existing_chunks)} indexed chunks")
    
    prompt = f"Generate up to {count} high-quality educational flashcards from the supplied context. Return strict JSON with top-level key 'flashcards' as a list. Each card must have question, answer, source_chunk_ids (list), and optional topic. Do not hallucinate; only use the provided context."
    
    # Retrieve diverse chunks
    chunks = retrieve_relevant(doc_id, "flashcards generation", top_k=DEFAULT_TOP_K, min_score=0.05)
    logger.info(f"[RAG] Retrieved {len(chunks)} candidate chunks for generation")
    
    if not chunks:
        logger.warning(f"[RAG] No relevant chunks retrieved for doc_id={doc_id}")
        raise ValueError("No relevant content found in document for flashcard generation")
    
    context = _build_context(chunks)
    logger.info(f"[RAG] Built context from {len(chunks)} chunks ({len(context)} chars)")
    
    system = "You are an educational content generation assistant. Use only the provided context to create flashcards. Return only valid JSON matching the schema."
    user = f"CONTEXT:\n{context}\n\nINSTRUCTIONS:\n{prompt}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    
    logger.info("[RAG] Calling OpenAI GPT for flashcard generation...")
    resp = chat_completion(messages, temperature=0.0, max_tokens=1500)
    text_out = resp["choices"][0]["message"]["content"]
    
    try:
        parsed = json.loads(text_out)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if not m:
            raise
        parsed = json.loads(m.group(0))

    cards = validate_flashcards(parsed)
    logger.info(f"[RAG] Flashcards validated: {len(cards)} cards generated")
    return cards[:count]


def rag_generate_quiz_from_doc(doc_id: str, count: int = 5) -> List[Dict[str, Any]]:
    """Generate quiz questions using an already-indexed document ID."""
    logger.info(f"[RAG] Quiz generation started with doc_id={doc_id}")
    
    # Verify document exists in index
    existing_chunks = get_document_chunks(doc_id)
    if not existing_chunks:
        raise ValueError(f"Document {doc_id} not found in index. Please upload and index first.")
    
    logger.info(f"[RAG] Document {doc_id} has {len(existing_chunks)} indexed chunks")
    
    prompt = f"Generate {count} multiple-choice questions (exactly 4 options each) from the supplied context. Return strict JSON with top-level key 'questions'. Each question must include question, options (4 unique strings), correct_answer, explanation (optional), source_chunk_ids (list), and topic. Use only the provided context. If you cannot produce enough valid questions, produce fewer."
    
    # Retrieve diverse chunks
    chunks = retrieve_relevant(doc_id, "quiz generation", top_k=DEFAULT_TOP_K, min_score=0.05)
    logger.info(f"[RAG] Retrieved {len(chunks)} candidate chunks for generation")
    
    if not chunks:
        logger.warning(f"[RAG] No relevant chunks retrieved for doc_id={doc_id}")
        raise ValueError("No relevant content found in document for quiz generation")
    
    context = _build_context(chunks)
    logger.info(f"[RAG] Built context from {len(chunks)} chunks ({len(context)} chars)")
    
    system = "You are an educational MCQ generation assistant. Use only the provided context to create questions. Return only valid JSON matching the schema."
    user = f"CONTEXT:\n{context}\n\nINSTRUCTIONS:\n{prompt}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    
    logger.info("[RAG] Calling OpenAI GPT for quiz generation...")
    resp = chat_completion(messages, temperature=0.0, max_tokens=1500)
    text_out = resp["choices"][0]["message"]["content"]
    
    try:
        parsed = json.loads(text_out)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}", text_out)
        if not m:
            raise
        parsed = json.loads(m.group(0))

    questions = validate_quiz(parsed)
    logger.info(f"[RAG] Quiz questions validated: {len(questions)} questions generated")
    return questions[:count]
