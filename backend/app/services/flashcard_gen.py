"""Flashcard generator from raw text and fallback extraction."""
import re
from typing import List, Dict, Any
from .validation_service import validate_flashcards

BULLET_CHARS = "○●■▪▫◆◇•\uf0b7\uf0a7\u2022\u2023\u25e6\u2043\u2219"


def _clean_text(text: str) -> str:
    cleaned = re.sub(rf"[{BULLET_CHARS}]", " ", text or "")
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    return " ".join(lines)


def _sentences(text: str) -> List[str]:
    text_clean = re.sub(rf"[{BULLET_CHARS}]", " ", text or "")
    paragraphs = re.split(r"\n\s*\n", text_clean)
    sentences: List[str] = []
    for para in paragraphs:
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        for line in lines:
            line_clean = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", line).strip()
            if not line_clean:
                continue
            if line_clean.endswith(";"):
                sentences.append(line_clean)
            else:
                raw = re.split(r"(?<=[.!?])\s+", line_clean)
                for s in raw:
                    s = s.strip()
                    if not s:
                        continue
                    if s[-1] not in ".!?;":
                        s += "."
                    if len(s.split()) >= 4 and len(s) >= 15:
                        sentences.append(s)
    return sentences


def _extract_term_question_answer(sentence: str) -> tuple[str, str] | None:
    text = re.sub(rf"[{BULLET_CHARS}]", "", sentence).strip()
    text = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", text).strip()
    if len(text.split()) < 4:
        return None

    # Handle SQL and programming statements meaningfully
    sql_match = re.match(
        r"^(?:EXAMPLE:\s*)?(DROP\s+INDEX|CREATE\s+INDEX|CREATE\s+TABLE|ALTER\s+TABLE|CREATE\s+CONSTRAINT|DROP\s+TABLE|ADD\s+CONSTRAINT)\b",
        text,
        re.IGNORECASE,
    )
    if sql_match:
        cmd = re.sub(r"\s+", " ", sql_match.group(1).upper().strip())
        return f"What is the purpose of the {cmd} statement in SQL?", text

    patterns = [
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:is|are|was|were|refers to|means|represents|describes|defines|includes|comprises)\s+(?P<detail>.+)$",
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:uses|helps|enables|supports|requires|involves|provides|allows|extracts|reuses|propagates|adjusts)\s+(?P<detail>.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            term = re.sub(r"^(?:a|an|the)\s+", "", match.group("term").strip(), flags=re.IGNORECASE)
            detail = match.group("detail").strip()
            if any(ch in term for ch in [";", "●", "○", "{", "}", "[", "]"]):
                continue
            if len(term.split()) <= 6 and len(detail.split()) >= 4:
                question = f"What is {term}?"
                if " uses " in text.casefold() or " helps " in text.casefold() or " enables " in text.casefold():
                    question = f"How does {term} work?"
                if " differ " in text.casefold() or " comparison " in text.casefold():
                    question = f"How does {term} differ from related concepts?"
                return question, text

    if ":" in text:
        prefix, suffix = text.rsplit(":", 1)
        prefix_clean = re.sub(r"^(?:example|note|tip|warning|syntax)\s*", "", prefix.strip(), flags=re.IGNORECASE).strip()
        prefix_clean = prefix_clean.rstrip(".-")
        if (
            prefix_clean
            and not any(ch in prefix_clean for ch in [";", "●", "○", "{", "}", "[", "]", "="])
            and len(prefix_clean.split()) <= 6
            and len(suffix.split()) >= 4
            and prefix_clean[0].isupper()
        ):
            return f"What is the key idea of {prefix_clean}?", text

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
        topic = (
            question.replace("What is the purpose of the ", "")
            .replace(" statement in SQL", "")
            .replace("What is the key idea of ", "")
            .replace("What is ", "")
            .replace("How does ", "")
            .replace("?", "")
            .strip()
        )
        raw_candidates.append({
            "id": len(raw_candidates) + 1,
            "question": question,
            "answer": answer,
            "type": "concept",
            "topic": topic or "General",
            "difficulty": "medium",
        })
        if len(raw_candidates) >= count:
            break

    if len(raw_candidates) < count:
        for sentence in sents:
            term_match = re.search(r"([A-Z][A-Za-z0-9\- ]{3,40})\s+(?:is|are|uses|helps|enables|refers to|means|represents)", sentence)
            if term_match and len(raw_candidates) < count:
                term = term_match.group(1).strip()
                if any(ch in term for ch in [";", "●", "○", "{", "}"]):
                    continue
                key = term.casefold()
                if key in {candidate["topic"].casefold() for candidate in raw_candidates}:
                    continue
                raw_candidates.append({
                    "id": len(raw_candidates) + 1,
                    "question": f"What is the role of {term}?",
                    "answer": sentence.strip(),
                    "type": "concept",
                    "topic": term,
                    "difficulty": "medium",
                })

    return validate_flashcards({"flashcards": raw_candidates}, count=count)


def generate_flashcards(text: str, count: int = 8) -> List[Dict[str, Any]]:
    """Generate flashcards using RAG if available, or fallback."""
    try:
        from .generation_service import rag_generate_flashcards
        return rag_generate_flashcards(text, count=count)
    except Exception:
        return _legacy_generate_flashcards(text, count=count)
