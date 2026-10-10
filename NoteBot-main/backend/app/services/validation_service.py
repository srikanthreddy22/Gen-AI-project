import json
from typing import List, Dict, Any


def validate_flashcards(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    seen_q = set()
    for i, c in enumerate(data.get("flashcards", [])):
        q = (c.get("question") or "").strip()
        a = (c.get("answer") or "").strip()
        if not q or not a:
            continue
        nq = " ".join(q.lower().split())
        if nq in seen_q:
            continue
        seen_q.add(nq)
        out.append({
            "id": c.get("id") or f"fc_{i}",
            "question": q,
            "answer": a,
            "source_chunk_ids": c.get("source_chunk_ids", []),
            "topic": c.get("topic", ""),
        })
    return out


def validate_quiz(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    seen_q = set()
    for i, qd in enumerate(data.get("questions", [])):
        q = (qd.get("question") or "").strip()
        opts = qd.get("options") or []
        if not q or not opts or len(opts) != 4:
            continue
        opts = [o.strip() for o in opts if o and isinstance(o, str)]
        if len(set(opts)) != 4:
            continue
        correct = qd.get("correct_answer") or qd.get("correct") or qd.get("answer")
        if not correct or correct not in opts:
            continue
        nq = " ".join(q.lower().split())
        if nq in seen_q:
            continue
        seen_q.add(nq)
        out.append({
            "id": qd.get("id") or f"q_{i}",
            "question": q,
            "options": opts,
            "correct_answer": correct,
            "correct_option_index": opts.index(correct),
            "explanation": qd.get("explanation", ""),
            "topic": qd.get("topic", ""),
            "source_chunk_ids": qd.get("source_chunk_ids", []),
        })
    return out
