"""Flashcard generator from raw text.

This module preserves the original heuristic generator as a fallback but will
use the RAG + OpenAI pipeline when an `OPENAI_API_KEY` is configured.
"""
import os
import re
from typing import List, Dict, Any

from .validation_service import validate_flashcards

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_KEY:
    try:
        from .generation_service import rag_generate_flashcards  # type: ignore
    except Exception:
        rag_generate_flashcards = None
else:
    rag_generate_flashcards = None


_STOPWORDS = set("a an the and or but in on at to for of with is are was were be been having have has".split())


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if len(s.split()) > 6]


def _classify(sentence: str) -> str:
    s = sentence.lower()
    if re.search(r"\bis\s+a\b|\bdefined\s+as\b|\brefers\s+to\b|\bmeans\b", s):
        return "definition"
    if re.search(r"\bvs\b|\bversus\b|\bcompared\b|\bdiffer", s):
        return "comparison"
    if re.search(r"\badvantage|benefit|improve|faster|better", s):
        return "benefit"
    if re.search(r"\bstep|process|algorithm|procedure|method", s):
        return "process"
    return "concept"


def _extract_term(sentence: str) -> str | None:
    m = re.match(r"^([A-Z][A-Za-z\s\-]+?)\s+(?:is|are|was|refers|defined)", sentence)
    if m:
        return m.group(1).strip()
    words = sentence.split()
    caps = [w.strip(".,;:") for w in words if w and w[0].isupper() and len(w) > 3]
    return caps[0] if caps else None


def _legacy_generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    sents = _sentences(text)
    if not sents:
        return []

    cards = []
    seen_terms = set()

    for i, s in enumerate(sents):
        if len(cards) >= count:
            break
        term = _extract_term(s)
        if not term or term.lower() in seen_terms:
            continue
        seen_terms.add(term.lower())
        card_type = _classify(s)
        if card_type == "definition":
            question = f"What is {term}?"
        elif card_type == "comparison":
            question = f"How does {term} compare to related concepts?"
        elif card_type == "benefit":
            question = f"What is the key advantage of {term}?"
        elif card_type == "process":
            question = f"How does the {term} process work?"
        else:
            question = f"Explain the concept of: {term}"

        cards.append({
            "id": i + 1,
            "question": question,
            "answer": s.strip(),
            "type": card_type,
        })

    return cards


def generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    # Prefer RAG generation when available
    if rag_generate_flashcards:
        try:
            return rag_generate_flashcards(text, count=count)
        except Exception:
            # fall back to legacy heuristics on failure
            pass
    return _legacy_generate_flashcards(text, count=count)
