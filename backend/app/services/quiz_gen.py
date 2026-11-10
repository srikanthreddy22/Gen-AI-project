import logging
import random
import re
from typing import Any

from .validation_service import is_similar_question

logger = logging.getLogger(__name__)

try:
    from .generation_service import rag_generate_quiz  # type: ignore
except ImportError:
    rag_generate_quiz = None


_STOP_CONCEPTS = {
    "a", "an", "the", "it", "this", "that", "these", "those", "they",
    "we", "i", "he", "she", "there", "here", "topic", "section", "chapter",
    "example", "examples", "note", "notes", "tip", "tips", "warning", "warnings",
    "eg", "e g", "ex", "etc", "ie", "i e", "syntax", "code", "table", "step", "page",
}

BULLET_CHARS = "○●■▪▫◆◇•\uf0b7\uf0a7\u2022\u2023\u25e6\u2043\u2219"


def _clean_text(text: str) -> str:
    cleaned = re.sub(rf"[{BULLET_CHARS}]", " ", text or "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+", " ", cleaned)
    return re.sub(r"[ \t]+", " ", cleaned.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        current = ""
        for line in paragraph.splitlines():
            line = line.strip()
            if not line:
                continue
            if current and re.match(r"^(?:topic|chapter|section|unit)\b", line, re.IGNORECASE):
                sentences.extend(re.split(r"(?<=[.!?])\s+", current))
                current = ""
            if current and re.search(r"[.!?][\"')\]]?$", current):
                sentences.extend(re.split(r"(?<=[.!?])\s+", current))
                current = line
            else:
                current = f"{current} {line}".strip()
        if current:
            sentences.extend(re.split(r"(?<=[.!?])\s+", current))
    cleaned = []
    for sentence in sentences:
        sentence = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", sentence).strip()
        if sentence and sentence[-1] not in ".!?":
            sentence += "."
        if sentence:
            cleaned.append(sentence)
    return cleaned


def _candidate_key(sentence: str) -> str:
    return re.sub(r"\W+", " ", sentence.casefold()).strip()


def _extract_term_and_statement(sentence: str) -> tuple[str, str] | None:
    text = sentence.strip()
    if len(text.split()) < 4:
        return None

    patterns = [
        r"^(?P<term>(?:CREATE|DROP|ALTER|SELECT|INSERT|UPDATE|DELETE|TRUNCATE|GRANT|REVOKE|COMMIT|ROLLBACK|WHERE|GROUP BY|HAVING|ORDER BY|JOIN|PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK|NOT NULL|INDEX|VIEW|TRIGGER)\b[A-Za-z0-9\-_\(\) ]{0,60}?)\s+(?:statement|clause|command|constraint|function|index|operation|query)?\s*(?:is|are|was|were|refers to|means|defines|represents|specifies|ensures|removes|adds|modifies|retrieves|executes|filters|sorts|groups|combines|controls)\s+(?P<detail>.+)$",
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:is|are|was|were|refers to|means|represents|describes|defines|includes|comprises)\s+(?P<detail>.+)$",
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:uses|uses\s+to|helps|helps\s+to|enables|supports|requires|involves|contains|provides|allows|operates by)\s+(?P<detail>.+)$",
        r"^(?P<term>[A-Z][A-Za-z0-9\- ]{2,80}?)\s+(?:adjusts|learns|extracts|reuses|propagates|reduces|improves|stores|translates|maps|removes|ensures|executes|performs|guarantees|manages)\s+(?P<detail>.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if not match:
            continue
        term = re.sub(r"^(?:a|an|the)\s+", "", match.group("term").strip(), flags=re.IGNORECASE)
        detail = match.group("detail").strip()
        if not term or len(term.split()) > 8:
            continue
        if any(ch in term for ch in [";", "●", "○", "{", "}", "[", "]"]):
            continue
        if term.split()[0].casefold() in _STOP_CONCEPTS:
            continue
        if len(detail.split()) < 3:
            continue
        return term, detail

    if ":" in text or " - " in text or " — " in text:
        delim = ":" if ":" in text else (" — " if " — " in text else " - ")
        prefix, suffix = text.rsplit(delim, 1)
        prefix_clean = re.sub(r"^(?:example|note|tip|warning|syntax)\s*", "", prefix.strip(), flags=re.IGNORECASE).strip().rstrip(".-")
        if (
            prefix_clean
            and not any(ch in prefix_clean for ch in [";", "●", "○", "{", "}", "[", "]", "="])
            and len(prefix_clean.split()) <= 8
            and len(suffix.split()) >= 3
            and prefix_clean.split()[0].casefold() not in _STOP_CONCEPTS
        ):
            return prefix_clean, suffix.strip()

    return None


def _make_question(term: str, statement: str) -> str:
    lower = statement.casefold()
    term_clean = term.strip()
    if any(marker in lower for marker in [" is a ", " is an ", " refers to ", " means ", " represents ", " defines "]):
        return f"Which statement best describes {term_clean}?"
    if any(marker in lower for marker in [" adjusts ", " learns ", " extracts ", " reuses ", " propagates ", " improves ", " performs ", " executes "]):
        return f"What is the primary function of {term_clean}?"
    if any(marker in lower for marker in ["removes", "deletes", "drops"]):
        return f"What is the effect of executing {term_clean}?"
    if any(marker in lower for marker in ["ensures", "guarantees", "prevents"]):
        return f"What does {term_clean} ensure in the system?"
    if " differ " in lower or " compared " in lower:
        return f"How does {term_clean} differ from related concepts?"
    return f"What is the key purpose of {term_clean}?"


def _candidate_statements(text: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for sentence in _split_sentences(_clean_text(text)):
        parsed = _extract_term_and_statement(sentence)
        if not parsed:
            continue
        term, detail = parsed
        statement = f"{term} {detail}" if not detail.startswith(term) else detail
        statement = re.sub(r"\s+", " ", statement).strip()
        if not statement.endswith("."):
            statement += "."
        key = _candidate_key(statement)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        candidates.append({"concept": term, "statement": statement})
    return candidates


def _generic_distractors(concept: str, correct: str) -> list[str]:
    concept_lower = concept.casefold()
    generic = [
        "Machine learning studies algorithms that learn patterns from data.",
        "A neural network is composed of layers of connected units that transform input features.",
        "Classification assigns inputs to predefined categories based on learned patterns.",
        "Regression estimates a continuous value from labeled examples.",
    ]
    if "deep learning" in concept_lower:
        generic = [
            "Machine learning studies algorithms that learn patterns from data.",
            "A neural network is composed of layers of connected units that transform input features.",
            "Backpropagation adjusts weights by propagating error signals through the network.",
            "Transfer learning reuses a pretrained model on a new task with less data and training time.",
        ]
    elif "network" in concept_lower or "ip" in concept_lower or "dns" in concept_lower or "routing" in concept_lower:
        generic = [
            "A router selects data paths across a network based on routing rules.",
            "An IP address uniquely identifies a device on a network.",
            "A firewall monitors and controls traffic according to security policies.",
            "DNS translates human-readable domain names into IP addresses.",
        ]
    elif "database" in concept_lower or "normalization" in concept_lower or "primary" in concept_lower or "table" in concept_lower or "index" in concept_lower or "constraint" in concept_lower:
        generic = [
            "Database normalization reduces duplication and improves data integrity.",
            "A primary key uniquely identifies each row in a table.",
            "A foreign key references a key in another table.",
            "First normal form requires each table cell to contain one atomic value.",
        ]

    unique = []
    seen = set()
    for option in generic + [correct]:
        key = re.sub(r"\W+", " ", option.casefold()).strip()
        if not option or key in seen or key == re.sub(r"\W+", " ", correct.casefold()).strip():
            continue
        seen.add(key)
        unique.append(option.strip())
        if len(unique) >= 3:
            break
    return unique


def _build_options(candidate: dict[str, str], candidates: list[dict[str, str]]) -> list[str]:
    correct = candidate["statement"]
    options = [correct]
    for other in candidates:
        if other is candidate:
            continue
        distractor = other["statement"]
        if distractor.casefold() == correct.casefold():
            continue
        if distractor not in options:
            options.append(distractor)
        if len(options) >= 4:
            break

    if len(options) < 4:
        for sentence in _split_sentences(_clean_text(candidate["statement"])):
            if sentence.casefold() == correct.casefold():
                continue
            if sentence not in options:
                options.append(sentence)
            if len(options) >= 4:
                break

    if len(options) < 4:
        for distractor in _generic_distractors(candidate["concept"], correct):
            if distractor.casefold() != correct.casefold() and distractor not in options:
                options.append(distractor)
            if len(options) >= 4:
                break

    unique = []
    seen = set()
    for option in options:
        key = re.sub(r"\W+", " ", option.casefold()).strip()
        if not option or key in seen or len(option.strip()) < 8:
            continue
        seen.add(key)
        unique.append(option.strip())
    if len(unique) < 4:
        for gd in _generic_distractors(candidate["concept"], correct):
            key = re.sub(r"\W+", " ", gd.casefold()).strip()
            if key not in seen and gd not in unique:
                seen.add(key)
                unique.append(gd.strip())
            if len(unique) >= 4:
                break
    if len(unique) < 2:
        unique = [correct, correct]
        unique = list(dict.fromkeys(unique))
    if len(unique) > 4:
        unique = unique[:4]
    random.shuffle(unique)
    return unique


def generate_quiz(text: str, count: int = 5) -> list[dict[str, Any]]:
    if not text:
        return []

    if rag_generate_quiz:
        try:
            return rag_generate_quiz(text, count=count)
        except Exception as exc:
            logger.warning("LLM quiz generation failed; using the local fallback: %s", exc)

    return _generate_quiz_locally(text, count=count)


def _generate_quiz_locally(
    text: str,
    count: int = 5,
    exclude_questions: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not text or count <= 0:
        return []

    candidates = _candidate_statements(text)
    if not candidates:
        return []

    exclusions = exclude_questions or []
    questions: list[dict[str, Any]] = []
    seen_concepts: set[str] = set()

    for candidate in candidates:
        if len(questions) >= count:
            break

        concept = candidate["concept"]
        if concept.casefold() in seen_concepts:
            continue

        question_text = _make_question(concept, candidate["statement"])
        normalized_question = re.sub(r"\W+", " ", question_text.casefold()).strip()
        if any(
            normalized_question == re.sub(r"\W+", " ", previous.casefold()).strip()
            or is_similar_question(question_text, previous, threshold=0.9)
            for previous in exclusions
        ):
            continue

        seen_concepts.add(concept.casefold())
        correct = candidate["statement"]
        options = _build_options(candidate, candidates)
        if len(options) < 4:
            continue

        questions.append({
            "question": question_text,
            "options": options,
            "correct": correct,
            "correct_answer": correct,
            "explanation": f"The document states: {correct}",
            "difficulty": "easy" if len(correct.split()) < 18 else "medium",
            "topic": concept,
            "source_chunk_ids": [],
        })

    return questions
