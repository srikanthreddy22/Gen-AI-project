from flask import Blueprint, request, jsonify
from ..services.summarizer import summarize

bp = Blueprint("summarize", __name__)

@bp.route("/summarize", methods=["POST"])
@bp.route("/summarize/", methods=["POST"])
def summarize_route():
    try:
        data = request.get_json(silent=True)
        if not data or "text" not in data:
            return jsonify({"error": "No text provided"}), 400

        text = data.get("text", "")
        print(f"Incoming text length: {len(text)}")

        if len(text.strip()) == 0:
            return jsonify({"error": "Empty text"}), 400

        method = data.get("method", "auto")
        bullet_count = min(int(data.get("bullet_count", 6)), 12)

        result = summarize(text, method=method, bullet_count=bullet_count)
        return jsonify(result)
    except Exception as e:
        print(f"Summarization error: {e}")
        return jsonify({"error": str(e)}), 500
