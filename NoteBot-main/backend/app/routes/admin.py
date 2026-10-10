import os
import shutil
import uuid
from flask import Blueprint, request, jsonify

from ..services import rag_service, vector_store

bp = Blueprint("admin", __name__)

ADMIN_KEY = os.getenv("ADMIN_API_KEY")


def _require_admin(req):
    key = req.headers.get("X-Admin-Key")
    if not ADMIN_KEY:
        return False, (False, "Admin API key not configured on server")
    if not key:
        return False, (False, "Missing X-Admin-Key header")
    if key != ADMIN_KEY:
        return False, (False, "Invalid admin key")
    return True, None


@bp.route("/admin/reindex", methods=["POST"])
def reindex_route():
    ok, err = _require_admin(request)
    if not ok:
        return jsonify({"error": err[1]}), 401

    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    text = data.get("text")
    doc_name = data.get("doc_name")

    if not doc_id and not text:
        return jsonify({"error": "Provide doc_id or text to reindex"}), 400

    # if text not provided, try to reconstruct from existing chunks
    if not text:
        existing = vector_store.get_document_chunks(doc_id)
        if not existing:
            return jsonify({"error": "Document not found and no text provided"}), 404
        # reconstruct approximate text
        text = "\n\n".join([c.get("chunk_text", "") for c in existing])

    # safe reindex strategy:
    # 1) prepare chunks+embeddings using rag_service.prepare_document_chunks into a temp DB
    # 2) atomically swap rows for doc_id from temp DB into main DB using ATTACH/transaction
    # 3) cleanup temp DB; on failure restore previous state (no deletion of old index until swap)
    db_path = vector_store.DB_PATH
    temp_db = db_path + f".tmp.reindex.{uuid.uuid4().hex}.db"
    try:
        # prepare chunks and embeddings without touching main DB
        new_doc_id, new_doc_name, chunks = rag_service.prepare_document_chunks(text, doc_name=doc_name)

        # validate prepared data
        if not chunks:
            return jsonify({"error": "No chunks generated"}), 400
        ids = [c.get("chunk_id") for c in chunks]
        if len(ids) != len(set(ids)):
            return jsonify({"error": "Duplicate chunk ids in prepared data"}), 500
        if any(not c.get("embedding") for c in chunks):
            return jsonify({"error": "Missing embeddings in prepared data"}), 500

        # write prepared chunks to a temporary DB file
        vector_store.add_document_chunks_to_dbpath(temp_db, new_doc_id, new_doc_name, chunks)

        # verify temp DB contains rows for this doc before swapping
        try:
            import sqlite3 as _sqlite
            tconn = _sqlite.connect(temp_db)
            tcur = tconn.cursor()
            tcur.execute("SELECT COUNT(1) FROM chunks WHERE doc_id=?", (new_doc_id,))
            cnt = tcur.fetchone()[0]
            tconn.close()
        except Exception:
            cnt = 0
        if not cnt:
            try:
                if os.path.exists(temp_db):
                    os.remove(temp_db)
            except Exception:
                pass
            return jsonify({"error": "Prepared index is empty; aborting"}), 500

        # backup current DB before swapping
        backup = db_path + ".bak"
        try:
            if os.path.exists(db_path):
                shutil.copy2(db_path, backup)
        except Exception:
            # if backup fails, abort to avoid risky replacement
            try:
                if os.path.exists(temp_db):
                    os.remove(temp_db)
            except Exception:
                pass
            return jsonify({"error": "Failed to create DB backup; aborting reindex"}), 500

        # perform atomic replace into main DB
        vector_store.atomic_replace_document(new_doc_id, temp_db)

        new_chunks = vector_store.get_document_chunks(new_doc_id)
        topic_groups = set(c.get("source_meta", {}).get("topic_group") for c in new_chunks)
        topic_groups.discard(None)

        # cleanup temp and backup
        try:
            if os.path.exists(temp_db):
                os.remove(temp_db)
        except Exception:
            pass
        try:
            if os.path.exists(backup):
                os.remove(backup)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "old_doc_id": doc_id,
            "document_id": new_doc_id,
            "chunks_created": len(new_chunks),
            "embeddings_created": len([c for c in new_chunks if c.get("embedding")]),
            "topic_groups": len(topic_groups),
            "message": "Document reindexed successfully"
        })
    except Exception:
        # attempt rollback from backup if it exists
        try:
            backup = db_path + ".bak"
            if os.path.exists(backup):
                shutil.copy2(backup, db_path)
        except Exception:
            pass
        # cleanup temp DB
        try:
            if os.path.exists(temp_db):
                os.remove(temp_db)
        except Exception:
            pass
        # do not expose internal error details
        return jsonify({"error": "Reindex failed"}), 500
    finally:
        try:
            if os.path.exists(temp_db):
                os.remove(temp_db)
        except Exception:
            pass


@bp.route("/admin/inspect_index", methods=["GET"])
def inspect_index():
    ok, err = _require_admin(request)
    if not ok:
        return jsonify({"error": err[1]}), 401

    doc_id = request.args.get("doc_id")
    if not doc_id:
        return jsonify({"error": "doc_id is required"}), 400

    chunks = vector_store.get_document_chunks(doc_id)
    if not chunks:
        return jsonify({"error": "Document not found"}), 404

    out_chunks = []
    for c in chunks:
        meta = c.get("source_meta", {}) or {}
        out_chunks.append({
            "chunk_id": c.get("chunk_id"),
            "chunk_index": c.get("chunk_index"),
            "preview": (c.get("chunk_text") or "")[:300],
            "section": meta.get("section"),
            "topic_group": meta.get("topic_group"),
            "has_embedding": bool(c.get("embedding")),
        })

    return jsonify({
        "document_id": doc_id,
        "document_name": chunks[0].get("doc_name") if chunks else None,
        "total_chunks": len(chunks),
        "chunks": out_chunks,
    })


@bp.route("/admin/inspect_retrieval", methods=["POST"])
def inspect_retrieval():
    ok, err = _require_admin(request)
    if not ok:
        return jsonify({"error": err[1]}), 401

    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    query = data.get("query")
    top_k = int(data.get("top_k", 8))
    candidate_k = int(data.get("candidate_k", 30))

    if not doc_id or not query:
        return jsonify({"error": "doc_id and query are required"}), 400

    # generate query embedding and candidates
    try:
        q_emb = rag_service.get_embeddings([query])[0]
    except Exception as e:
        return jsonify({"error": "Embedding generation failed", "details": str(e)}), 500

    candidates = vector_store.similarity_search(doc_id, q_emb, top_k=candidate_k, min_score=0.0)
    cand_list = []
    for score, ch in candidates:
        meta = ch.get("source_meta", {}) or {}
        cand_list.append({
            "chunk_id": ch.get("chunk_id"),
            "chunk_index": ch.get("chunk_index"),
            "preview": (ch.get("chunk_text") or "")[:250],
            "topic_group": meta.get("topic_group"),
            "section": meta.get("section"),
            "score": float(score),
        })

    # call retrieve_relevant to get selected diverse chunks
    selected = rag_service.retrieve_relevant(doc_id, query, top_k=top_k, min_score=0.0, candidate_k=candidate_k, debug=True)
    sel_list = []
    for c in selected:
        sel_list.append({
            "chunk_id": c.get("chunk_id"),
            "chunk_index": c.get("chunk_index"),
            "preview": (c.get("chunk_text") or "")[:250],
            "topic_group": c.get("topic_group"),
            "section": c.get("section"),
            "score": float(c.get("score", 0.0)),
            "debug": c.get("debug")
        })

    return jsonify({
        "document_id": doc_id,
        "query": query,
        "candidate_count": len(cand_list),
        "candidates": cand_list,
        "selected_count": len(sel_list),
        "selected": sel_list,
    })
