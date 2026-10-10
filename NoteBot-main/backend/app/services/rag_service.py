"""RAG utilities: chunking, embedding generation, storage, and retrieval."""
import os
import hashlib
import uuid
import math
import logging
from typing import List, Dict, Any
from .openai_service import get_embeddings, is_insufficient_quota
from .vector_store import add_document_chunks, get_document_chunks, similarity_search, delete_document_embeddings

logger = logging.getLogger(__name__)


DEFAULT_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_SIZE", "3000"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "500"))


def _doc_id_for_text(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"doc_{h}"


def _get_index_embeddings(texts: List[str]) -> List[List[float]]:
    try:
        return get_embeddings(texts)
    except Exception as exc:
        if not is_insufficient_quota(exc):
            raise
        logger.warning(
            "[RAG] OpenAI embedding quota exhausted; using local fallback embeddings",
            exc_info=True,
        )
        return [_approx_embedding(text) for text in texts]


def _split_into_paragraphs(text: str) -> List[str]:
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    out = []
    buffer = []
    for p in paras:
        buffer.append(p)
        # if buffer length grows large, flush
        if sum(len(x) for x in buffer) >= DEFAULT_CHUNK_CHARS:
            out.append("\n".join(buffer))
            buffer = []
    if buffer:
        out.append("\n".join(buffer))
    return out


def _smart_chunk(text: str, chunk_size_chars: int | None = None, overlap_chars: int | None = None) -> List[Dict[str, Any]]:
    # allow runtime overrides; default to module-level settings
    chunk_size_chars = int(chunk_size_chars or DEFAULT_CHUNK_CHARS)
    overlap_chars = int(overlap_chars or DEFAULT_CHUNK_OVERLAP)
    paras = _split_into_paragraphs(text)
    chunks = []
    current = ""
    idx = 0
    for p in paras:
        if not current:
            current = p
        elif len(current) + len(p) + 1 <= chunk_size_chars:
            current += "\n" + p
        else:
            chunks.append(current)
            # create overlap
            overlap = current[-overlap_chars:] if overlap_chars < len(current) else current
            current = overlap + "\n" + p
        # avoid extremely short chunks
        if len(current) >= chunk_size_chars:
            chunks.append(current)
            current = ""
        idx += 1
    if current:
        chunks.append(current)

    out = []
    for i, c in enumerate(chunks):
        out.append({
            "chunk_id": str(uuid.uuid4()),
            "chunk_index": i,
            "chunk_text": c,
            "source_meta": {},
        })
    return out


def process_document(text: str, doc_name: str | None = None, force_reindex: bool = False) -> str:
    """Chunk, embed, and store document. Returns doc_id."""
    doc_id = _doc_id_for_text(text)
    if not force_reindex:
        existing = get_document_chunks(doc_id)
        if existing:
            return doc_id
    # remove old
    delete_document_embeddings(doc_id)

    chunks = _smart_chunk(text)
    texts = [c["chunk_text"] for c in chunks]
    # batch embeddings
    embs = _get_index_embeddings(texts)
    for c, e in zip(chunks, embs):
        c["embedding"] = e
    # create lightweight topic grouping and store as metadata
    try:
        _assign_topic_groups(chunks)
    except Exception:
        # grouping is best-effort; continue if it fails
        pass

    add_document_chunks(doc_id, doc_name or "uploaded", chunks)
    return doc_id


def prepare_document_chunks(text: str, doc_name: str | None = None):
    """Prepare chunks and embeddings for a document without modifying the main DB.
    Returns (doc_id, chunks).
    """
    doc_id = _doc_id_for_text(text)
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


def _approx_embedding(text: str) -> List[float]:
    """Best-effort local approximation for degraded environments only.

    This should never be the primary retrieval behavior in production. It is
    retained only as a last-resort fallback when the configured embedding model
    is unavailable.
    """
    h = sum(ord(c) for c in (text or "")) % 1000
    return [((h + i) % 100) / 100.0 for i in range(3)]


def _guess_section_heading(chunk_text: str) -> str:
    # heuristics: first non-empty line under 80 chars
    lines = [l.strip() for l in chunk_text.split("\n") if l.strip()]
    if not lines:
        return ""
    first = lines[0]
    if len(first) < 80 and len(first.split()) < 10:
        return first
    # otherwise try to find a short line later
    for l in lines[:4]:
        if len(l) < 80 and any(c.isalpha() for c in l):
            return l[:80]
    return first[:80]


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


def retrieve_relevant(doc_id: str, query: str, top_k: int = 8, min_score: float = 0.0, candidate_k: int = 30, debug: bool = False) -> List[Dict[str, Any]]:
    """Diversity-aware retrieval: get candidate_k then select a diverse set of top_k chunks.
    Returns selected chunks with added 'score' and 'topic_group' in `source_meta`.
    """
    doc_chunks = get_document_chunks(doc_id)
    logger.info(f"[RAG] retrieve_relevant doc_id={doc_id} query={query!r} total_chunks={len(doc_chunks)}")

    if not doc_chunks:
        logger.warning(f"[RAG] No indexed chunks for doc_id={doc_id}")
        return []

    use_real_query_embedding = os.getenv("RAG_USE_REAL_QUERY_EMBEDDINGS", "0") == "1" or bool(os.getenv("OPENAI_API_KEY"))
    if use_real_query_embedding:
        try:
            q_emb = get_embeddings([query], model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))[0]
            logger.info(f"[RAG] Query embedding generated for doc_id={doc_id}")
        except Exception as exc:
            logger.warning(f"[RAG] Real embedding failed for query={query!r}: {exc}. Falling back to deterministic approximation.")
            q_emb = _approx_embedding(query)
    else:
        logger.info(f"[RAG] Query embedding fallback selected for doc_id={doc_id} (no OpenAI key configured)")
        q_emb = _approx_embedding(query)

    candidates = similarity_search(doc_id, q_emb, top_k=candidate_k, min_score=min_score)
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
        doc_chunks = get_document_chunks(doc_id)
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
            for se in selected_embs:
                if _cosine(se, c.get("embedding", [])) > 0.995:
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
