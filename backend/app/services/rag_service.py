"""RAG utilities: chunking, embedding generation, storage, and retrieval."""
import os
import hashlib
import uuid
import math
import logging
import re
import time
from typing import List, Dict, Any
from .embedding_service import get_embeddings
from .vector_store import add_document_chunks, get_document_chunks, similarity_search

logger = logging.getLogger(__name__)


DEFAULT_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))


def _doc_id_for_text(text: str, owner_id: str | None = None) -> str:
    source = f"{owner_id}\0{text}" if owner_id else text
    h = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"doc_{h}"


def _get_index_embeddings(texts: List[str]) -> List[List[float]]:
    embeddings = get_embeddings(texts)
    if len(embeddings) != len(texts):
        raise ValueError("Embedding service returned a different number of vectors than input chunks")
    return embeddings


def _choose_chunk_end(text: str, start: int, limit: int) -> int:
    if limit == len(text):
        return limit
    minimum = start + max(1, (limit - start) // 2)
    window = text[start:limit]

    # 1. Look for section heading boundaries: prefer ending before a new section heading
    section_matches = [
        start + match.start()
        for match in re.finditer(r"\n+(?:#{1,4}\s+|Topic\s+[A-Za-z0-9]+:|Chapter\s+\d+|Section\s+\d+)", window)
        if start + match.start() >= minimum
    ]
    if section_matches:
        return section_matches[-1]

    # 2. Look for paragraph boundaries
    paragraph_boundaries = [
        start + match.end()
        for match in re.finditer(r"\n[ \t]*\n+", window)
        if start + match.end() >= minimum
    ]
    if paragraph_boundaries:
        return paragraph_boundaries[-1]

    # 3. Look for code statement boundaries (semicolon followed by newline, common in SQL)
    code_statement_boundaries = [
        start + match.end()
        for match in re.finditer(r";\s*\n+", window)
        if start + match.end() >= minimum
    ]
    if code_statement_boundaries:
        return code_statement_boundaries[-1]

    # 4. Look for sentence boundaries
    sentence_boundaries = [
        start + match.end()
        for match in re.finditer(r"""[.!?]["')\]]*\s+""", window)
        if start + match.end() >= minimum
    ]
    if sentence_boundaries:
        return sentence_boundaries[-1]

    # 5. Look for whitespace boundaries
    whitespace_boundaries = [
        index + 1
        for index in range(start, limit)
        if text[index].isspace() and index + 1 >= minimum
    ]
    return whitespace_boundaries[-1] if whitespace_boundaries else limit


def _choose_overlap_start(text: str, start: int, end: int, overlap_chars: int) -> int:
    if overlap_chars == 0:
        return end
    target = max(start + 1, end - overlap_chars)
    boundaries = [
        start + match.end()
        for match in re.finditer(
            r"""\n[ \t]*\n+|;\s*\n+|[.!?]["')\]]*\s+""",
            text[start:end],
        )
    ]
    boundaries = [
        candidate for candidate in boundaries if start < candidate < end
    ]
    if boundaries:
        return min(boundaries, key=lambda candidate: abs(candidate - target))

    whitespace_boundaries = [
        index + 1
        for index in range(start, end)
        if text[index].isspace()
    ]
    whitespace_boundaries = [
        candidate for candidate in whitespace_boundaries if start < candidate < end
    ]
    if not whitespace_boundaries:
        return target
    return min(whitespace_boundaries, key=lambda candidate: abs(candidate - target))


def _chunk_page(
    text: str,
    page_number: int | None,
    chunk_size_chars: int,
    overlap_chars: int,
    first_chunk_index: int,
) -> List[Dict[str, Any]]:
    normalized = text.strip()
    if not normalized:
        return []

    chunks = []
    start = 0
    while start < len(normalized):
        limit = min(start + chunk_size_chars, len(normalized))
        end = _choose_chunk_end(normalized, start, limit)
        chunk_text = normalized[start:end].strip()
        if chunk_text:
            source_meta = {}
            if page_number is not None:
                source_meta["page_number"] = page_number
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "chunk_index": first_chunk_index + len(chunks),
                "chunk_text": chunk_text,
                "source_meta": source_meta,
            })
        if end >= len(normalized):
            break
        next_start = _choose_overlap_start(normalized, start, end, overlap_chars)
        start = next_start if next_start > start else end
    return chunks


def _smart_chunk(
    text: str,
    chunk_size_chars: int | None = None,
    overlap_chars: int | None = None,
    pages: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    chunk_size_chars = int(chunk_size_chars or DEFAULT_CHUNK_CHARS)
    overlap_chars = int(overlap_chars or DEFAULT_CHUNK_OVERLAP)
    if chunk_size_chars <= 0 or overlap_chars < 0 or overlap_chars >= chunk_size_chars:
        raise ValueError("Chunk size must be positive and overlap must be smaller than the chunk size")

    source_pages = pages or [{"page_number": None, "text": text}]
    chunks: List[Dict[str, Any]] = []
    for page in source_pages:
        page_chunks = _chunk_page(
            str(page.get("text") or ""),
            page.get("page_number"),
            chunk_size_chars,
            overlap_chars,
            len(chunks),
        )
        chunks.extend(page_chunks)
    return chunks


def process_document(
    text: str,
    doc_name: str | None = None,
    force_reindex: bool = False,
    owner_id: str | None = None,
    pages: List[Dict[str, Any]] | None = None,
) -> str:
    """Chunk, embed, and store document. Returns doc_id."""
    if not text.strip():
        raise ValueError("Cannot index an empty document")
    doc_id = _doc_id_for_text(text, owner_id=owner_id)
    if not force_reindex:
        lookup_started = time.perf_counter()
        existing = get_document_chunks(doc_id, user_id=owner_id)
        logger.info("[RAG] Existing-index lookup completed in %.3fs (%d chunks)", time.perf_counter() - lookup_started, len(existing))
        if existing:
            return doc_id
    chunk_started = time.perf_counter()
    chunks = _smart_chunk(text, pages=pages)
    logger.info("[RAG] Chunked document in %.3fs (%d chunks)", time.perf_counter() - chunk_started, len(chunks))
    texts = [c["chunk_text"] for c in chunks]
    embedding_started = time.perf_counter()
    embs = _get_index_embeddings(texts)
    logger.info("[RAG] Generated embeddings in %.3fs (%d chunks)", time.perf_counter() - embedding_started, len(embs))
    for c, e in zip(chunks, embs):
        c["embedding"] = e
    # create lightweight topic grouping and store as metadata
    grouping_started = time.perf_counter()
    try:
        _assign_topic_groups(chunks)
    except Exception:
        # grouping is best-effort; continue if it fails
        logger.exception("[RAG] Topic grouping failed")
    logger.info("[RAG] Topic grouping completed in %.3fs", time.perf_counter() - grouping_started)

    storage_started = time.perf_counter()
    add_document_chunks(doc_id, doc_name or "uploaded", chunks, user_id=owner_id)
    logger.info("[RAG] ChromaDB storage completed in %.3fs (%d chunks)", time.perf_counter() - storage_started, len(chunks))
    return doc_id


def prepare_document_chunks(
    text: str,
    doc_name: str | None = None,
    owner_id: str | None = None,
):
    """Prepare chunks and embeddings for a document without modifying the main DB.
    Returns (doc_id, chunks).
    """
    doc_id = _doc_id_for_text(text, owner_id=owner_id)
    chunks = _smart_chunk(text)
    texts = [c["chunk_text"] for c in chunks]
    # batch embeddings
    embs = _get_index_embeddings(texts)
    for c, e in zip(chunks, embs):
        c["embedding"] = e
    # topic grouping best-effort
    try:
        _assign_topic_groups(chunks)
    except Exception:
        pass
    return doc_id, (doc_name or "uploaded"), chunks


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _guess_section_heading(chunk_text: str) -> str:
    lines = [l.strip() for l in chunk_text.split("\n") if l.strip()]
    if not lines:
        return ""
    code_indicators = {"select", "insert", "update", "delete", "create", "drop", "alter", "example:", "note:", "tip:", "constraint"}
    for l in lines[:5]:
        stripped = l.lstrip("-*•# ").strip()
        if not stripped or len(stripped) > 80:
            continue
        first_word = stripped.split()[0].lower() if stripped.split() else ""
        if first_word in code_indicators or stripped.endswith(";"):
            continue
        if l.startswith("#"):
            return stripped[:80]
        if re.match(r"^(?:topic|chapter|section|unit|part)\b", stripped, re.IGNORECASE):
            return stripped[:80]
        if len(stripped.split()) <= 8 and any(c.isalpha() for c in stripped):
            return stripped[:80]
    return lines[0][:80]


def _assign_topic_groups(chunks: List[Dict[str, Any]], threshold: float = 0.78) -> None:
    """Assign simple topic groups by greedy clustering on embeddings.
    Mutates `chunks`, setting `source_meta.topic_group` and `source_meta.section`.
    """
    # greedy clustering using group centroids: tighter groups, less chance to merge
    groups: List[List[int]] = []
    emb_list = [c.get("embedding", []) for c in chunks]
    centroids: List[List[float]] = []
    for i, emb in enumerate(emb_list):
        placed = False
        for gi, centroid in enumerate(centroids):
            s = _cosine(emb, centroid)
            if s >= threshold:
                groups[gi].append(i)
                # update centroid
                grp_embs = [emb_list[idx] for idx in groups[gi]]
                # average
                centroid = [sum(vals) / len(vals) for vals in zip(*grp_embs)] if grp_embs else centroid
                centroids[gi] = centroid
                placed = True
                break
        if not placed:
            groups.append([i])
            centroids.append(emb)

    # annotate chunks
    for gi, group in enumerate(groups, start=1):
        label = f"topic_{gi}"
        # produce a short human label from the largest chunk in group
        best_idx = max(group, key=lambda k: len(chunks[k]["chunk_text"]))
        section = _guess_section_heading(chunks[best_idx]["chunk_text"]) or label
        for idx in group:
            meta = chunks[idx].get("source_meta", {}) or {}
            meta["topic_group"] = label
            meta["section"] = section
            chunks[idx]["source_meta"] = meta

    # fallback: if everything collapsed into one group, try naive heading-based split
    if len(groups) <= 1:
        # look for explicit 'Topic' headings in chunk texts
        heading_map = {}
        for i, c in enumerate(chunks):
            heading = _guess_section_heading(c.get('chunk_text', ''))
            if heading and heading.lower().startswith('topic'):
                heading_map.setdefault(heading, []).append(i)
        if len(heading_map) > 1:
            # reassign groups based on headings
            groups = list(heading_map.values())
            for gi, group in enumerate(groups, start=1):
                label = f"topic_{gi}"
                best_idx = max(group, key=lambda k: len(chunks[k]["chunk_text"]))
                section = _guess_section_heading(chunks[best_idx]["chunk_text"]) or label
                for idx in group:
                    meta = chunks[idx].get("source_meta", {}) or {}
                    meta["topic_group"] = label
                    meta["section"] = section
                    chunks[idx]["source_meta"] = meta


def retrieve_relevant(
    doc_id: str,
    query: str,
    top_k: int = 8,
    min_score: float = 0.0,
    candidate_k: int = 30,
    debug: bool = False,
    user_id: str | None = None,
) -> List[Dict[str, Any]]:
    """Diversity-aware retrieval: get candidate_k then select a diverse set of top_k chunks.
    Returns selected chunks with added 'score' and 'topic_group' in `source_meta`.
    """
    doc_chunks = get_document_chunks(doc_id, user_id=user_id)
    logger.info(f"[RAG] retrieve_relevant doc_id={doc_id} query={query!r} total_chunks={len(doc_chunks)}")

    if not doc_chunks:
        logger.warning(f"[RAG] No indexed chunks for doc_id={doc_id}")
        return []

    query_embeddings = get_embeddings([query])
    if len(query_embeddings) != 1:
        raise ValueError("Embedding service did not return a vector for the query")
    q_emb = query_embeddings[0]
    if not q_emb:
        raise ValueError("Embedding service returned an empty query vector")
    if any(len(chunk.get("embedding") or []) != len(q_emb) for chunk in doc_chunks):
        raise ValueError("Stored document embeddings do not match the query embedding model")

    candidates = similarity_search(
        doc_id,
        q_emb,
        top_k=candidate_k,
        min_score=min_score,
        user_id=user_id,
    )
    logger.info(f"[RAG] doc_id={doc_id} candidate_count={len(candidates)}")
    for score, ch in candidates[:5]:
        logger.info(f"[RAG] candidate score={score:.4f} chunk_id={ch.get('chunk_id')} chunk_preview={ch.get('chunk_text','')[:80]}")

    if not candidates:
        return []

    # convert to list of dicts and dedupe near-duplicate texts
    seen = set()
    cand_list: List[Dict[str, Any]] = []
    for score, ch in candidates:
        txt = ch["chunk_text"].strip()
        key = txt[:200]
        if key in seen:
            continue
        seen.add(key)
        ch_copy = ch.copy()
        ch_copy["score"] = score
        # ensure topic_group exists; if not, we'll cluster these candidates on the fly
        meta = ch_copy.get("source_meta") or {}
        ch_copy["topic_group"] = meta.get("topic_group")
        ch_copy["section"] = meta.get("section")
        cand_list.append(ch_copy)

    # if candidates cover too few groups but document contains multiple groups,
    # add one representative chunk from missing groups to allow diversity
    try:
        doc_chunks = get_document_chunks(doc_id, user_id=user_id)
        doc_groups = set((c.get('source_meta') or {}).get('topic_group') for c in doc_chunks)
        doc_groups.discard(None)
        cand_groups = set(c.get('topic_group') for c in cand_list if c.get('topic_group'))
        missing = [g for g in doc_groups if g not in cand_groups]
        if missing and len(doc_groups) > 1:
            # pick largest chunk per missing group
            for g in missing:
                group_items = [c for c in doc_chunks if (c.get('source_meta') or {}).get('topic_group') == g]
                if not group_items:
                    continue
                best = max(group_items, key=lambda x: len(x.get('chunk_text','')))
                bcopy = best.copy()
                bcopy['score'] = 0.0
                bcopy['topic_group'] = g
                bcopy['section'] = (best.get('source_meta') or {}).get('section')
                cand_list.append(bcopy)
    except Exception:
        pass

    # if no topic_group metadata, perform lightweight clustering on candidate embeddings
    if not any(c.get("topic_group") for c in cand_list):
        # cluster only the candidate set
        emb_list = [c.get("embedding", []) for c in cand_list]
        groups = []  # list of lists of indices
        centroids = []
        for i, emb in enumerate(emb_list):
            placed = False
            for gi, centroid in enumerate(centroids):
                if _cosine(emb, centroid) >= 0.78:
                    groups[gi].append(i)
                    # update centroid
                    grp_embs = [emb_list[idx] for idx in groups[gi]]
                    centroid = [sum(vals) / len(vals) for vals in zip(*grp_embs)] if grp_embs else centroid
                    centroids[gi] = centroid
                    placed = True
                    break
            if not placed:
                groups.append([i])
                centroids.append(emb)
        # assign topic_group names
        for gi, group in enumerate(groups, start=1):
            label = f"topic_{gi}"
            for idx in group:
                cand_list[idx]["topic_group"] = label
                cand_list[idx]["section"] = _guess_section_heading(cand_list[idx]["chunk_text"]) or label

    # compute group total scores
    group_scores = {}
    for c in cand_list:
        g = c.get("topic_group") or "topic_0"
        group_scores[g] = group_scores.get(g, 0.0) + float(c.get("score", 0.0))
    total_group_score = sum(group_scores.values()) or 1.0

    # select chunks in round-robin order across groups to improve diversity
    selected: List[Dict[str, Any]] = []
    selected_embs: List[List[float]] = []

    # group -> items sorted by score
    group_items_map = {}
    for g in group_scores.keys():
        items = [c for c in cand_list if c.get("topic_group") == g]
        items.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        group_items_map[g] = items

    # order groups by descending total score so higher-score groups get earlier picks
    groups_ordered = sorted(group_scores.keys(), key=lambda g: group_scores.get(g, 0.0), reverse=True)

    # round-robin pick one from each group while avoiding redundancy
    pointers = {g: 0 for g in groups_ordered}
    while len(selected) < top_k:
        progressed = False
        for g in groups_ordered:
            items = group_items_map.get(g, [])
            p = pointers[g]
            if p >= len(items):
                continue
            c = items[p]
            pointers[g] = p + 1
            # redundancy check
            redundant = False
            for selected_chunk, selected_embedding in zip(selected, selected_embs):
                if (
                    selected_chunk.get("topic_group") == c.get("topic_group")
                    and _cosine(selected_embedding, c.get("embedding", [])) > 0.995
                ):
                    redundant = True
                    break
            if redundant:
                continue
            selected.append(c)
            selected_embs.append(c.get("embedding", []))
            progressed = True
            if len(selected) >= top_k:
                break
        if not progressed:
            # no more selectable items
            break

    if debug or os.getenv("RAG_DEBUG") == "1":
        # attach debug info to return; consumer can log it
        for c in selected:
            c["debug"] = {
                "candidate_count": len(cand_list),
                "group_scores": group_scores,
            }

    return selected
