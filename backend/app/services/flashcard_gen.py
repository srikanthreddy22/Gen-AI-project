"""Flashcard generator from raw text and fallback extraction."""
import re
from typing import List, Dict, Any
from .validation_service import validate_flashcards


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return " ".join(lines)


def _sentences(text: str) -> List[str]:
    cleaned = _clean_text(text)
    raw = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences: List[str] = []
    for sentence in raw:
        sentence = sentence.strip()
        if not sentence:
            continue
        if sentence[-1] not in ".!?":
            sentence += "."
        if len(sentence.split()) >= 6 and len(sentence) >= 20:
            sentences.append(sentence)
    return sentences


def _extract_term_question_answer(sentence: str) -> tuple[str, str] | None:
    text = sentence.strip()
    patterns = [
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:is|are|was|were|refers to|means|represents|describes|defines|includes|comprises)\s+(?P<detail>.+)$",
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:uses|helps|enables|supports|requires|involves|provides|allows|extracts|reuses|propagates|adjusts)\s+(?P<detail>.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            term = re.sub(r"^(?:a|an|the)\s+", "", match.group("term").strip(), flags=re.IGNORECASE)
            detail = match.group("detail").strip()
            if len(term.split()) <= 6 and len(detail.split()) >= 5:
                question = f"What is {term}?"
                if " uses " in text.casefold() or " helps " in text.casefold() or " enables " in text.casefold():
                    question = f"How does {term} work?"
                if " differ " in text.casefold() or " comparison " in text.casefold():
                    question = f"How does {term} differ from related concepts?"
                return question, text

    if ":" in text:
        prefix, suffix = text.rsplit(":", 1)
        if len(prefix.split()) <= 8 and len(suffix.split()) >= 5:
            term = prefix.strip().rstrip(".-")
            if term:
                return f"What is the key idea of {term}?", text

    return None


def _legacy_generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    """Heuristic fallback extraction for generating meaningful study cards when offline."""
    sents = _sentences(text)
    if not sents:
        return []

    raw_candidates = []
    seen_keys = set()
    for sentence in sents:
        candidate = _extract_term_question_answer(sentence)
        if not candidate:
            continue
        question, answer = candidate
        key = re.sub(r"\W+", " ", question.casefold()).strip()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        raw_candidates.append({
            "id": len(raw_candidates) + 1,
            "question": question,
            "answer": answer,
            "type": "concept",
            "topic": question.replace("What is ", "").replace("How does ", "").replace("What is the key idea of ", "").replace("?", "").strip(),
        })
        if len(raw_candidates) >= count:
            break

    if len(raw_candidates) < count:
        for sentence in sents:
            term_match = re.search(r"([A-Z][A-Za-z0-9\- ]{3,40})\s+(?:is|are|uses|helps|enables|refers to|means|represents)", sentence)
            if term_match and len(raw_candidates) < count:
                term = term_match.group(1).strip()
                key = term.casefold()
                if key in {candidate["topic"].casefold() for candidate in raw_candidates}:
                    continue
                raw_candidates.append({
                    "id": len(raw_candidates) + 1,
                    "question": f"What is the role of {term}?",
                    "answer": sentence.strip(),
                    "type": "concept",
                    "topic": term,
                })

    return validate_flashcards({"flashcards": raw_candidates}, count=count)


def generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    """Generate flashcards using RAG if available, or fallback."""
    try:
        from .generation_service import rag_generate_flashcards
        return rag_generate_flashcards(text, count=count)
    except Exception:
        return _legacy_generate_flashcards(text, count=count)
