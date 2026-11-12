import os
import re
import shutil
import tempfile
import time
import uuid
import logging
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename
from ..extensions import db
from ..services.persistence_service import get_document_by_vector_id, register_document
from ..services.rag_service import process_document
from ..services.embedding_service import EmbeddingServiceError
from ..services.vector_store import delete_document_embeddings

bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "txt", "md"}

BULLET_CHARS = "○●■▪▫◆◇•\uf0b7\uf0a7\u2022\u2023\u25e6\u2043\u2219"
BULLET_PREFIX_RE = re.compile(rf"^[ \t]*[{BULLET_CHARS}]+[ \t]*")
INLINE_BULLET_RE = re.compile(rf"[ \t]+[{BULLET_CHARS}]+[ \t]*")
HEADER_FOOTER_PATTERNS = [
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*[-—]\s*\d+\s*[-—]\s*$"),
]


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_extracted_text(text: str) -> str:
    """Normalize line endings, remove meaningless symbols/headers while preserving code and paragraphs."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # De-hyphenate words split at line breaks
    text = re.sub(r"(\b[a-zA-Z]{2,})-\n([a-zA-Z]{2,}\b)", r"\1\2", text)

    raw_lines = text.split("\n")
    cleaned_lines = []
    for line in raw_lines:
        line_str = line.strip()
        if not line_str:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        # Filter out standalone page numbers or headers
        if any(pat.match(line_str) for pat in HEADER_FOOTER_PATTERNS):
            continue

        # Normalize decorative bullet symbols to clean markdown list markers
        if BULLET_PREFIX_RE.match(line_str):
            line_str = "- " + BULLET_PREFIX_RE.sub("", line_str).strip()

        # Handle inline bullets that mashed two concepts together
        if INLINE_BULLET_RE.search(line_str):
            line_str = INLINE_BULLET_RE.sub("\n- ", line_str)

        # Remove stray non-printable control characters
        line_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+", " ", line_str).strip()

        if line_str:
            # If line_str contains newlines from the inline bullet split
            for sub_line in line_str.split("\n"):
                sub_clean = sub_line.strip()
                if sub_clean:
                    cleaned_lines.append(sub_clean)

    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()
    return "\n".join(cleaned_lines)


def _extract_document(filepath: str, ext: str) -> tuple[str, str, list[dict]]:
    if ext == "pdf":
        pages = []
        try:
            import fitz
            with fitz.open(filepath) as doc:
                for page_number, page in enumerate(doc, start=1):
                    rect = page.rect
                    page_height = rect.height if rect else 1000.0

                    blocks = page.get_text("blocks")
                    extracted_blocks = []
                    for b in blocks:
                        if len(b) < 5:
                            continue
                        x0, y0, x1, y1, b_text = b[0], b[1], b[2], b[3], b[4]
                        if not isinstance(b_text, str) or not b_text.strip():
                            continue

                        # Header/footer filter at margin limits
                        is_top_margin = y1 <= 0.05 * page_height
                        is_bottom_margin = y0 >= 0.95 * page_height
                        b_stripped = b_text.strip()
                        if (is_top_margin or is_bottom_margin) and any(pat.match(b_stripped) for pat in HEADER_FOOTER_PATTERNS):
                            continue

                        extracted_blocks.append((y0, x0, b_text))

                    if extracted_blocks:
                        extracted_blocks.sort(key=lambda item: (item[0], item[1]))
                        raw_page_text = "\n\n".join(item[2] for item in extracted_blocks)
                    else:
                        raw_page_text = page.get_text()

                    page_text = clean_extracted_text(raw_page_text)
                    if page_text:
                        pages.append({"page_number": page_number, "text": page_text})
        except Exception as e:
            logger.exception("PyMuPDF extraction failed for %s", filepath)
            return "", "PDF is unreadable or text extraction failed.", []

        cleaned = "\n\n".join(page["text"] for page in pages)
        if not cleaned:
            return "", "PDF contains no readable text or is an image-only scan.", []
        return cleaned, "", pages
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            cleaned = clean_extracted_text(text)
            if not cleaned:
                return "", "Text file is empty or contains no readable characters.", []
            return cleaned, "", [{"page_number": None, "text": cleaned}]
        except Exception as e:
            logger.exception("Text extraction failed for %s", filepath)
            return "", f"Text extraction failed: {str(e)}", []


def _extract_text(filepath: str, ext: str) -> tuple[str, str]:
    text, error, _pages = _extract_document(filepath, ext)
    return text, error


def _page_count(filepath: str, ext: str) -> int:
    if ext != "pdf":
        return 0
    import fitz
    with fitz.open(filepath) as doc:
        return len(doc)


def _persist_uploaded_file(filepath: str, filename: str) -> str:
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    safe_name = secure_filename(filename) or "document"
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = os.path.abspath(os.path.join(upload_folder, stored_name))
    shutil.copy2(filepath, stored_path)
    return stored_path


@bp.route("/upload", methods=["POST"], strict_slashes=False)
@bp.route("/upload/", methods=["POST"])
@jwt_required()
def upload_route():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not _allowed(file.filename):
        return jsonify({"error": "Unsupported file type"}), 415

    ext = file.filename.rsplit(".", 1)[1].lower()
    
    logger.info("[Upload] Received %s (type: %s)", file.filename, ext)

    tmp_path = ""
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp_path = tmp.name

    page_count = 0
    file_size = 0
    storage_path = None
    user_id = get_jwt_identity()
    try:
        save_started = time.perf_counter()
        file.save(tmp_path)
        file_size = os.path.getsize(tmp_path)
        logger.info("[Upload] Temporary file saved in %.3fs (%d bytes)", time.perf_counter() - save_started, file_size)
        extraction_started = time.perf_counter()
        text, error_msg, pages = _extract_document(tmp_path, ext)
        logger.info("[Upload] Text extraction completed in %.3fs (%d chars, %d pages)", time.perf_counter() - extraction_started, len(text), len(pages))
        if text and ext == "pdf":
            page_count_started = time.perf_counter()
            page_count = _page_count(tmp_path, ext)
            logger.info("[Upload] PDF page count read in %.3fs (%d pages)", time.perf_counter() - page_count_started, page_count)
    except Exception as e:
        text, error_msg = "", f"Failed to save temporary file: {str(e)}"

    if not text:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.warning("[Upload] Extraction failed for %s: %s", file.filename, error_msg)
        try:
            register_document(
                vector_id=None,
                original_name=file.filename,
                content="",
                file_size=file_size,
                status="extraction_failed",
                user_id=user_id,
            )
        except Exception:
            logger.exception("[DB] Failed to save extraction failure status")
            return jsonify({"error": "Document processing status could not be saved"}), 503
        return jsonify({"error": error_msg or "Unable to extract readable text"}), 400

    word_count = len(text.split())
    logger.info("[Upload] Extracted %d chars and %d words from %s", len(text), word_count, file.filename)
    
    # Optional check for minimum threshold
    if len(text) < 10:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        try:
            register_document(
                vector_id=None,
                original_name=file.filename,
                content=text,
                file_size=file_size,
                page_count=page_count,
                status="rejected",
                user_id=user_id,
            )
        except Exception:
            logger.exception("[DB] Failed to save rejected document status")
            return jsonify({"error": "Document processing status could not be saved"}), 503
        return jsonify({"error": "Text too short to be meaningful"}), 400

    doc_id = None
    # Index the document and persist its source file and relational metadata.
    indexing_started = time.perf_counter()
    try:
        doc_id = process_document(
            text,
            doc_name=file.filename,
            force_reindex=True,
            owner_id=user_id,
            pages=pages,
        )
        logger.info("[Upload] Indexing completed in %.3fs: %s", time.perf_counter() - indexing_started, doc_id)
    except EmbeddingServiceError as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.warning("[Upload] Embedding service unavailable: %s", e)
        return jsonify({"error": "Embeddings are not configured. Set GEMINI_API_KEY."}), 503
    except Exception as e:
        logger.exception("[Upload] Indexing failed after %.3fs for %s: %s", time.perf_counter() - indexing_started, file.filename, e)
    metadata_started = time.perf_counter()
    try:
        existing_document = get_document_by_vector_id(doc_id) if doc_id else None
        if (
            existing_document
            and existing_document.storage_path
            and os.path.isfile(existing_document.storage_path)
        ):
            storage_path = existing_document.storage_path
        else:
            storage_path = _persist_uploaded_file(tmp_path, file.filename)
        register_document(
            vector_id=doc_id,
            original_name=file.filename,
            content=text,
            file_size=file_size,
            storage_path=storage_path,
            page_count=page_count,
            status="indexed" if doc_id else "index_failed",
            user_id=user_id,
        )
        logger.info("[Upload] File and SQL metadata persisted in %.3fs (status: %s)", time.perf_counter() - metadata_started, "indexed" if doc_id else "index_failed")
    except Exception:
        if storage_path and os.path.exists(storage_path):
            os.unlink(storage_path)
        logger.exception("[DB] Failed to persist uploaded document metadata")
        return jsonify({"error": "Document metadata could not be saved"}), 503
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return jsonify({
        "text": text,
        "filename": file.filename,
        "word_count": word_count,
        "char_count": len(text),
        "doc_id": doc_id,
        "indexed": doc_id is not None
    })


@bp.route("/upload/text", methods=["POST"], strict_slashes=False)
@bp.route("/upload/text/", methods=["POST"])
@jwt_required()
def index_text_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "No text provided"}), 400
    cleaned_input = clean_extracted_text(text.strip())
    if len(cleaned_input) < 10:
        return jsonify({"error": "Text too short to be meaningful"}), 400

    doc_name = data.get("doc_name")
    if not isinstance(doc_name, str) or not doc_name.strip():
        doc_name = "pasted-text"
    user_id = get_jwt_identity()

    try:
        doc_id = process_document(
            cleaned_input,
            doc_name=doc_name,
            force_reindex=True,
            owner_id=user_id,
        )
    except EmbeddingServiceError as e:
        logger.warning("[Upload] Embedding service unavailable: %s", e)
        return jsonify({"error": "Embeddings are not configured. Set GEMINI_API_KEY."}), 503
    except Exception as exc:
        logger.exception("[RAG] Failed to index pasted text")
        try:
            register_document(
                vector_id=None,
                original_name=doc_name,
                content=cleaned_input,
                file_size=len(cleaned_input.encode("utf-8")),
                status="index_failed",
                user_id=user_id,
            )
        except Exception:
            logger.exception("[DB] Failed to save pasted-text indexing failure status")
            return jsonify({"error": "Document processing status could not be saved"}), 503
        return jsonify({"error": f"Document indexing failed: {exc}"}), 500

    try:
        register_document(
            vector_id=doc_id,
            original_name=doc_name,
            content=cleaned_input,
            file_size=len(cleaned_input.encode("utf-8")),
            user_id=user_id,
        )
    except Exception:
        logger.exception("[DB] Failed to persist pasted document metadata")
        return jsonify({"error": "Document metadata could not be saved"}), 503

    logger.info("[RAG] Pasted text indexed: doc_id=%s words=%s", doc_id, len(cleaned_input.split()))
    return jsonify({
        "doc_id": doc_id,
        "indexed": True,
        "word_count": len(cleaned_input.split()),
        "char_count": len(cleaned_input),
    })


@bp.route("/documents/<string:doc_id>", methods=["DELETE"])
@jwt_required()
def delete_document_route(doc_id):
    user_id = get_jwt_identity()
    document = get_document_by_vector_id(doc_id)
    if document is None or document.user_id != user_id:
        return jsonify({"error": "Document not found"}), 404

    storage_path = document.storage_path
    try:
        db.session.delete(document)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("[DB] Failed to delete document %s", doc_id)
        return jsonify({"error": "Document could not be deleted"}), 503

    try:
        delete_document_embeddings(doc_id, user_id=user_id)
    except Exception:
        logger.exception("[RAG] Document %s was deleted but vector cleanup failed", doc_id)
        return jsonify({
            "error": "Document was deleted, but vector cleanup failed",
            "deleted": True,
        }), 503

    if storage_path and os.path.isfile(storage_path):
        try:
            os.remove(storage_path)
        except OSError:
            logger.exception("[UPLOAD] Document %s was deleted but its source file could not be removed", doc_id)
            return jsonify({
                "error": "Document was deleted, but its source file could not be removed",
                "deleted": True,
            }), 503

    return jsonify({"deleted": True, "doc_id": doc_id})
