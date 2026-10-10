import os
import random
import re
import math
from collections import Counter
from typing import List, Dict, Any

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_KEY:
    try:
        from .generation_service import rag_generate_quiz  # type: ignore
    except Exception:
        rag_generate_quiz = None
else:
    rag_generate_quiz = None


_STOPWORDS = set(
    "a an the and or but in on at to for of with is are was were be been being have has had do does did will would could should may might shall that this these those it its we our they their i me my he she him her you your".split()
)


def _clean_text(text: str) -> str:
    """Remove OCR artefacts, stray symbols and normalize whitespace."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _sentence_filter(sentence: str) -> bool:
    words = sentence.split()
    return len(words) >= 8 and all(ch not in sentence for ch in "<>#@%$&*")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z]+", text)]


def _extract_key_phrases(text: str, top_n: int = 8) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    doc_freq = Counter()
    tf_per_sent = []
    for s in sentences:
        tokens = [t for t in _tokenize(s) if t not in _STOPWORDS and len(t) > 3]
        tf = Counter(tokens)
        tf_per_sent.append(tf)
        doc_freq.update(set(tokens))

    N = len(sentences)
    scores = Counter()
    for tf in tf_per_sent:
        for term, freq in tf.items():
            idf = math.log((N + 1) / (doc_freq[term] + 1))
            scores[term] += freq * idf

    return [t.title() for t, _ in scores.most_common(top_n)]


def _extract_candidates(sentence: str) -> list[str]:
    terms = []
    for match in re.finditer(r"\b([A-Z][a-zA-Z0-9]{3,}(?:\s+[A-Z][a-zA-Z0-9]{3,})*)\b", sentence):
        phrase = match.group(1).strip()
        if phrase.lower() not in _STOPWORDS and len(phrase) > 4:
            terms.append(phrase)

    if not terms:
        words = [w for w in re.findall(r"[a-zA-Z]{5,}", sentence) if w.lower() not in _STOPWORDS]
        freq = Counter(words)
        terms = [w.title() for w, _ in freq.most_common(3)]
    return terms


def _choose_blank(sentence: str, candidates: list[str]) -> tuple[str | None, str | None]:
    for phrase in candidates:
        if phrase and phrase.lower() in sentence.lower():
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            blanked = pattern.sub("_____", sentence, count=1)
            if blanked != sentence:
                return phrase, blanked
    return None, None


def _generate_distractors(correct: str, all_terms: list[str], count: int = 3) -> list[str]:
    distractors = []
    for term in all_terms:
        if term.lower() != correct.lower() and term not in distractors:
            distractors.append(term)
        if len(distractors) >= count:
            break
    return distractors[:count]


def generate_quiz(text: str, count: int = 5) -> list[dict]:
    """Public API – generate a list of MCQs from *text*. If OpenAI key is configured
    the RAG-based generator will be used; otherwise the legacy heuristic generator
    is used as a fallback.
    """
    if not text:
        return []

    if rag_generate_quiz:
        try:
            return rag_generate_quiz(text, count=count)
        except Exception:
            pass

    return _generate_quiz_locally(text, count=count)


def _generate_quiz_locally(text: str, count: int = 5) -> list[dict]:
    if not text:
        return []

    random.seed(42)
    clean = _clean_text(text)
    sentences = [s for s in _split_sentences(clean) if _sentence_filter(s)]
    if not sentences:
        return []

    global_terms = _extract_key_phrases(clean, top_n=40)
    questions = []

    for sentence in sentences:
        if len(questions) >= count:
            break

        candidates = _extract_candidates(sentence)
        local_terms = [t for t in candidates if len(t.split()) <= 4]
        if not local_terms:
            local_terms = _extract_key_phrases(sentence, top_n=3)

        correct, question_text = _choose_blank(sentence, local_terms)
        if not correct:
            continue

        distractors = _generate_distractors(correct, [t for t in global_terms if t.lower() != correct.lower()], count=3)
        if len(distractors) < 3:
            continue

        options = distractors + [correct]
        random.shuffle(options)
        difficulty = (
            "hard" if len(sentence.split()) > 20 else
            "medium" if len(sentence.split()) > 14 else
            "easy"
        )

        if len(set(options)) != 4:
            continue

        questions.append({
            "question": question_text,
            "options": options,
            "correct": correct,
            "difficulty": difficulty,
        })

    return questions
