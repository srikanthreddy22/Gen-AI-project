import os
import tempfile
import logging
from flask import Blueprint, request, jsonify
from ..services.rag_service import process_document

bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "txt", "md"}

def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_extracted_text(text: str) -> str:
    """Strip extra whitespace, normalize line breaks, remove empty lines."""
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(cleaned_lines)

def _extract_text(filepath: str, ext: str) -> tuple[str, str]:
    if ext == "pdf":
        text_chunks = []
        try:
            import fitz
            with fitz.open(filepath) as doc:
                for page in doc:
                    page_text = page.get_text()
                    if page_text:
                        text_chunks.append(page_text)
        except Exception as e:
            print("PyMuPDF import or extraction failed:", e)
            return "", "PDF engine initialization failed. PyMuPDF dependency missing or PDF file is unreadable."

        text = "\n".join(text_chunks)
        cleaned = clean_extracted_text(text)
        if not cleaned:
            return "", "PDF contains no readable text or is an image-only scan."
        return cleaned, ""
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            cleaned = clean_extracted_text(text)
            if not cleaned:
                return "", "Text file is empty or contains no readable characters."
            return cleaned, ""
        except Exception as e:
            return "", f"Text extraction failed: {str(e)}"

@bp.route("/upload/", methods=["POST"])
def upload_route():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not _allowed(file.filename):
        return jsonify({"error": "Unsupported file type"}), 415

    ext = file.filename.rsplit(".", 1)[1].lower()
    
    print(f"Uploaded file: {file.filename} (Type: {ext})")

    tmp_path = ""
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        file.save(tmp_path)
        text, error_msg = _extract_text(tmp_path, ext)
    except Exception as e:
        text, error_msg = "", f"Failed to save temporary file: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to delete temp file: {e}")

    if not text:
        print(f"Extraction failed for {file.filename}: {error_msg}")
        return jsonify({"error": error_msg or "Unable to extract readable text"}), 400

    word_count = len(text.split())
    print(f"Extracted length: {len(text)} chars, {word_count} words")
    
    # Optional check for minimum threshold
    if len(text) < 10:
        return jsonify({"error": "Text too short to be meaningful"}), 400

    # Index document for RAG
    try:
        doc_id = process_document(text, doc_name=file.filename, force_reindex=True)
        logger.info(f"[RAG] Document indexed: {doc_id} from {file.filename}")
    except Exception as e:
        logger.error(f"[RAG] Document indexing failed: {str(e)}")
        doc_id = None  # Still return text if indexing fails

    return jsonify({
        "text": text,
        "filename": file.filename,
        "word_count": word_count,
        "char_count": len(text),
        "doc_id": doc_id,
        "indexed": doc_id is not None
    })


@bp.route("/upload/text/", methods=["POST"])
def index_text_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "No text provided"}), 400
    if len(text.strip()) < 10:
        return jsonify({"error": "Text too short to be meaningful"}), 400

    doc_name = data.get("doc_name")
    if not isinstance(doc_name, str) or not doc_name.strip():
        doc_name = "pasted-text"

    try:
        doc_id = process_document(text.strip(), doc_name=doc_name, force_reindex=True)
    except Exception as exc:
        logger.exception("[RAG] Failed to index pasted text")
        return jsonify({"error": f"Document indexing failed: {exc}"}), 500

    logger.info("[RAG] Pasted text indexed: doc_id=%s words=%s", doc_id, len(text.split()))
    return jsonify({
        "doc_id": doc_id,
        "indexed": True,
        "word_count": len(text.split()),
        "char_count": len(text.strip()),
    })
