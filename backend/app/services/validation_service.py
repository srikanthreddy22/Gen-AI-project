import logging
import math
import re
import unicodedata
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
_STOPWORDS = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was", "were", "be", "been", "this", "that", "it"}
_OPTION_WARNING_THRESHOLD = 0.72
_OPTION_REJECTION_THRESHOLD = 0.90

BULLET_CHARS = "○●■▪▫◆◇•\uf0b7\uf0a7\u2022\u2023\u25e6\u2043\u2219"


def _content_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").casefold())) - _STOPWORDS


def _answer_is_supported(answer: str, source_text: str) -> bool:
    normalized_answer = _normalize_text(answer)
    normalized_source = _normalize_text(source_text)
    if not normalized_answer or not normalized_source:
        return False
    if normalized_answer in normalized_source:
        return True

    answer_tokens = _content_tokens(answer)
    if not answer_tokens:
        return False
    source_tokens = _content_tokens(source_text)
    if len(answer_tokens) == 1:
        return next(iter(answer_tokens)) in source_tokens
    overlap = len(answer_tokens & source_tokens)
    required_overlap = max(1, math.ceil(len(answer_tokens) * 0.35))
    return overlap >= required_overlap


def _normalize_text(text: str) -> str:
    """Normalize Unicode text, punctuation, and whitespace for comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"[^\W_]+", text, re.UNICODE))


def _token_set(text: str) -> set:
    norm = _normalize_text(text)
    return set(norm.split()) - _STOPWORDS


def _option_similarity(left: str, right: str) -> float:
    """Return token-set Jaccard similarity for a lightweight review signal."""
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def is_similar_question(q1: str, q2: str, threshold: float = 0.60) -> bool:
    """Determine whether two questions are identical or obvious near-duplicates."""
    n1 = _normalize_text(q1)
    n2 = _normalize_text(q2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    if n1 in n2 or n2 in n1:
        return True
    
    tokens1 = _token_set(q1)
    tokens2 = _token_set(q2)
    if not tokens1 or not tokens2:
        return False
    
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    jaccard = len(intersection) / len(union)
    return jaccard >= threshold


def validate_flashcards(
    data: Dict[str, Any],
    count: int = 8,
    valid_pages: Optional[set[int]] = None,
) -> List[Dict[str, Any]]:
    """Validate and filter flashcards ensuring clear questions and explanatory answers."""
    raw_cards = data.get("flashcards", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    
    out = []
    seen_questions = []

    for i, c in enumerate(raw_cards):
        if not isinstance(c, dict):
            continue
            
        raw_q = c.get("question") or ""
        raw_a = c.get("answer") or ""

        # Reject questions containing raw bullet symbols or stray semicolons
        if any(ch in raw_q for ch in ["○", "●", "■", "▪", "▫", "◆", "◇", "\uf0b7", "\uf0a7"]):
            continue
        if ";" in raw_q:
            continue
        if re.search(r"key idea of\s+(?:example|drop|create|alter|select|insert|update)\b", raw_q, re.IGNORECASE):
            continue

        q = raw_q.strip()
        a = raw_a.strip()
        card_type = (c.get("type") or "concept").strip().lower()
        topic = (c.get("topic") or "").strip()
        difficulty = str(c.get("difficulty") or "medium").strip().lower()

        # Clean stray bullet characters from answer
        a = re.sub(rf"[{BULLET_CHARS}]", "", a).strip()
        
        # 1. Length checks
        if len(q) < 10 or len(a) < 15:
            continue
            
        # 2. Must look like a question
        if not q.endswith("?") and not any(q.lower().startswith(w) for w in ["what", "how", "why", "when", "where", "who", "which", "explain", "describe", "compare"]):
            q = q + "?"
            
        # 3. Reject bad patterns (e.g. meta questions or broken fragments)
        q_lower = q.lower()
        if any(bad in q_lower for bad in ["according to the text", "in the passage", "the author states", "as mentioned above"]):
            continue
        if q_lower in {"what is this?", "explain.", "what is data?"}:
            continue

        # 4. Answer must not simply be the question
        if _normalize_text(q) == _normalize_text(a):
            continue
            
        # 5. Duplicate check against existing cards in this batch
        if any(is_similar_question(q, seen_q, threshold=0.65) for seen_q in seen_questions):
            continue

        seen_questions.append(q)
        validated_card = {
            "id": i + 1,
            "question": q,
            "answer": a,
            "type": card_type if card_type in {"definition", "process", "comparison", "benefit", "concept"} else "concept",
            "topic": topic[:255] or "General",
            "difficulty": difficulty if difficulty in {"easy", "medium", "hard"} else "medium",
            "source_chunk_ids": c.get("source_chunk_ids", []),
        }
        source_page = c.get("source_page")
        if isinstance(source_page, int) and not isinstance(source_page, bool) and source_page > 0:
            if valid_pages is None or source_page in valid_pages:
                validated_card["source_page"] = source_page
        out.append(validated_card)
        
        if len(out) >= count:
            break

    return out


def _reused_distractor_pattern(options: List[str], other_options: List[str]) -> bool:
    """Detect repeated full-option or near-duplicate distractors across questions."""
    if not options or not other_options:
        return False
    current_norms = [_normalize_text(opt) for opt in options]
    other_norms = [_normalize_text(opt) for opt in other_options]

    for current in current_norms:
        for other in other_norms:
            if not current or not other:
                continue
            if current == other:
                return True
            if current in other or other in current:
                return True
            similarity = _option_similarity(current, other)
            if similarity >= _OPTION_REJECTION_THRESHOLD:
                return True
    return False


def validate_quiz(
    data: Dict[str, Any],
    exclude_questions: Optional[List[str]] = None,
    count: int = 5,
    source_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Validate and deduplicate quiz questions against current batch and previous questions."""
    raw_questions = data.get("questions", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    exclusions = exclude_questions or []
    
    out = []
    seen_in_batch = []
    seen_distractors = []

    for i, qd in enumerate(raw_questions):
        if not isinstance(qd, dict):
            continue
            
        raw_q = qd.get("question") or ""
        if any(ch in raw_q for ch in ["○", "●", "■", "▪", "▫", "◆", "◇", "\uf0b7", "\uf0a7"]):
            continue

        q = raw_q.strip()
        opts = qd.get("options") or []
        explanation = (qd.get("explanation") or "").strip()
        difficulty = (qd.get("difficulty") or "medium").strip().lower()
        topic = (qd.get("topic") or "").strip()

        # Clean stray bullet characters from explanation
        explanation = re.sub(rf"[{BULLET_CHARS}]", "", explanation).strip()
        
        # 1. Reject incomplete, blank-based, or non-interrogative question stems.
        if (
            len(q) < 12
            or not q.endswith("?")
            or re.search(r"_{2,}|\.{3,}|\[\s*\]", q)
            or not re.match(r"^(what|which|how|why|when|where|who|can|does|do|is|are|in|for)\b", q, re.IGNORECASE)
        ):
            continue
        if source_text and not (_content_tokens(q) & _content_tokens(source_text)):
            continue

        # 2. Accept exactly four choices for this quiz flow and ensure no duplicates.
        if not isinstance(opts, list) or len(opts) != 4:
            continue
        if any(not isinstance(option, str) for option in opts):
            continue
        cleaned_opts = [re.sub(rf"[{BULLET_CHARS}]", "", option).strip() for option in opts]
        normalized_options = [_normalize_text(option) for option in cleaned_opts]
        if any(not option for option in cleaned_opts) or len(set(normalized_options)) != len(cleaned_opts):
            continue

        similar_option_pairs = [
            (left, right, _option_similarity(cleaned_opts[left], cleaned_opts[right]))
            for left in range(len(cleaned_opts))
            for right in range(left + 1, len(cleaned_opts))
            if normalized_options[left] != normalized_options[right]
            and _option_similarity(cleaned_opts[left], cleaned_opts[right]) >= _OPTION_WARNING_THRESHOLD
        ]
        for left, right, similarity in similar_option_pairs:
            logger.warning(
                "Quiz question %r has similar options %s and %s (Jaccard %.2f)",
                q,
                chr(65 + left),
                chr(65 + right),
                similarity,
            )
        if any(similarity >= _OPTION_REJECTION_THRESHOLD for _, _, similarity in similar_option_pairs):
            continue

        # 3. Correct answer validity and exactly one correct option.
        correct = qd.get("correct") or qd.get("correct_answer") or qd.get("answer")
        if not correct:
            continue
        correct_cleaned = re.sub(rf"[{BULLET_CHARS}]", "", str(correct)).strip()
        matching = [
            option for option, normalized_option in zip(cleaned_opts, normalized_options)
            if normalized_option == _normalize_text(correct_cleaned)
        ]
        if len(matching) != 1:
            continue
        correct_str = matching[0]
        if source_text and not _answer_is_supported(correct_str, source_text):
            continue

        incorrect_opts = [option for option in cleaned_opts if option != correct_str]
        if len(incorrect_opts) != 3:
            continue

        # 4. Reject cross-question repeated distractor pools.
        repeated_distractor = False
        for seen_question in seen_distractors:
            if _reused_distractor_pattern(incorrect_opts, seen_question):
                logger.warning("Rejected repeated distractor pattern across quiz questions: %r", q)
                repeated_distractor = True
                break
        if repeated_distractor:
            continue

        # 5. Check for duplicates against previous questions (session exclusions)
        if any(is_similar_question(q, prev_q, threshold=0.58) for prev_q in exclusions):
            continue

        # 6. Check for duplicates within current batch
        if any(is_similar_question(q, seen_q, threshold=0.58) for seen_q in seen_in_batch):
            continue

        # 7. Fallback explanation if missing
        if not explanation:
            explanation = f"'{correct_str}' is the correct answer based on the provided document."

        seen_in_batch.append(q)
        seen_distractors.append(incorrect_opts)
        out.append({
            "id": i + 1,
            "question": q,
            "options": cleaned_opts,
            "correct": correct_str,
            "correct_answer": correct_str,
            "explanation": explanation,
            "difficulty": difficulty if difficulty in {"easy", "medium", "hard"} else "medium",
            "topic": topic,
            "source_chunk_ids": qd.get("source_chunk_ids", []),
        })
        
        if len(out) >= count:
            break

    return out
