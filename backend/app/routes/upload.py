import os
import tempfile
import logging
from flask import Blueprint, request, jsonify
from ..demo_mode import demo_mode_enabled

bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)
DEMO_SUCCESS_MESSAGE = "PDF uploaded successfully. Demo study materials are ready!"

ALLOWED_EXTENSIONS = {"pdf", "txt", "md"}

def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_extracted_text(text: str) -> str:
    """Strip extra whitespace, normalize line breaks, remove empty lines."""
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(cleaned_lines)

def _extract_text(filepath: str, ext: str, demo_mode: bool = False) -> tuple[str, str]:
    if ext == "pdf":
        text_chunks = []
        try:
            import fitz
            with fitz.open(filepath) as doc:
                if doc.needs_pass and not doc.authenticate(""):
                    return "", "This PDF is password-protected. Remove the password and try again."
                if doc.page_count == 0:
                    return "", "This PDF contains no pages."
                pages = doc[:3] if demo_mode else doc
                for page in pages:
                    page_text = page.get_text()
                    if page_text:
                        text_chunks.append(page_text)
                    if demo_mode and sum(map(len, text_chunks)) >= 12000:
                        break
        except Exception as e:
            logger.warning("PDF text extraction failed: %s", e)
            return "", "This PDF is corrupted or unreadable. Please upload a valid PDF."

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


def process_document(*args, **kwargs):
    """Load the original RAG pipeline only when normal mode needs it."""
    from ..services.rag_service import process_document as rag_process_document

    return rag_process_document(*args, **kwargs)


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
    demo_mode = demo_mode_enabled()
    
    print(f"Uploaded file: {file.filename} (Type: {ext})")

    tmp_path = ""
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        file.save(tmp_path)
        text, error_msg = _extract_text(tmp_path, ext, demo_mode=demo_mode)
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

    if demo_mode:
        from ..services.demo_service import register_document

        doc_id, materials = register_document()
        materials["summary"]["stats"]["input_words"] = word_count
        return jsonify({
            "text": text,
            "filename": file.filename,
            "word_count": word_count,
            "char_count": len(text),
            "doc_id": doc_id,
            "indexed": True,
            "demo_mode": True,
            "message": (
                DEMO_SUCCESS_MESSAGE
                if ext == "pdf"
                else "Document uploaded successfully. Demo study materials are ready!"
            ),
            **materials,
        })

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

    if demo_mode_enabled():
        from ..services.demo_service import register_document

        doc_id, materials = register_document()
        return jsonify({
            "doc_id": doc_id,
            "indexed": True,
            "word_count": len(text.split()),
            "char_count": len(text.strip()),
            "demo_mode": True,
            "message": "Demo study materials are ready; they are not derived from the pasted text.",
            **materials,
        })

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
