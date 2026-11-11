from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
import logging
import sys

from .config import Config
from .extensions import db, migrate, jwt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def _normalize_cors_origins(raw_value):
    origins = [
        "https://note-bot-genai.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    if raw_value is None:
        return origins
    if isinstance(raw_value, list):
        for item in raw_value:
            if item not in origins:
                origins.append(item)
        return origins
    sanitized = str(raw_value).strip()
    if not sanitized or sanitized == "*":
        return origins
    if sanitized.lower().startswith("cors_origins="):
        sanitized = sanitized.split("=", 1)[1].strip()
    if sanitized.startswith("[") and sanitized.endswith("]"):
        sanitized = sanitized[1:-1]
    for item in sanitized.split(","):
        item = item.strip().replace(" ", "")
        if item and item not in origins:
            origins.append(item)
    return origins


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB
    app.config['CORS_ORIGINS'] = _normalize_cors_origins(app.config.get('CORS_ORIGINS'))

    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*",
                "methods": [
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "OPTIONS",
                ],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Requested-With",
                ],
                "supports_credentials": True,
            }
        },
        supports_credentials=True,
    )

    @app.before_request
    def handle_options_preflight():
        if request.method == "OPTIONS":
            response = app.make_default_options_response()
            origin = request.headers.get("Origin")
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            req_headers = request.headers.get("Access-Control-Request-Headers")
            if req_headers:
                response.headers["Access-Control-Allow-Headers"] = req_headers
            else:
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response

    @app.after_request
    def attach_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        response = jsonify({
            "error": e.description or str(e),
            "code": e.code,
        })
        response.status_code = e.code
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e):
        logger.exception("Unhandled server exception: %s", e)
        response = jsonify({
            "error": "An internal server error occurred",
            "code": 500,
        })
        response.status_code = 500
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        return response

    # Optional infrastructure dependencies may not be installed in local unit-test environments.
    if hasattr(db, 'init_app'):
        db.init_app(app)

    from . import models  # noqa: F401

    if hasattr(migrate, 'init_app'):
        migrate.init_app(app, db)
    if hasattr(jwt, 'init_app'):
        jwt.init_app(app)

    from .routes.summarize import bp as summarize_bp
    from .routes.flashcards import bp as flashcards_bp
    from .routes.quiz import bp as quiz_bp
    from .routes.upload import bp as upload_bp, upload_route, index_text_route
    from .routes.export import bp as export_bp
    from .routes.admin import bp as admin_bp
    from .routes.auth import bp as auth_bp
    from .routes.chat import bp as chat_bp
    from .models import RevokedToken

    app.register_blueprint(summarize_bp, url_prefix='/api')
    app.register_blueprint(flashcards_bp, url_prefix='/api')
    app.register_blueprint(quiz_bp, url_prefix='/api')
    app.register_blueprint(upload_bp, url_prefix='/api')
    app.register_blueprint(export_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api')

    @jwt.token_in_blocklist_loader
    def is_token_revoked(jwt_header, jwt_payload):
        return db.session.get(RevokedToken, jwt_payload["jti"]) is not None

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({"error": "Access token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_response(error):
        return jsonify({"error": "Invalid access token"}), 401

    @jwt.revoked_token_loader
    def revoked_token_response(jwt_header, jwt_payload):
        return jsonify({"error": "Access token has been revoked"}), 401

    @jwt.unauthorized_loader
    def missing_token_response(error):
        return jsonify({"error": "Authentication is required"}), 401

    if app.config.get("AUTO_CREATE_SCHEMA"):
        with app.app_context():
            db.create_all()

    @app.route('/')
    def home():
        return jsonify({"status": "Backend Running Successfully"})

    @app.route('/health')
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'version': '1.0.0'})

    @app.route('/upload', methods=['POST'], strict_slashes=False)
    @app.route('/upload/', methods=['POST'])
    def root_upload():
        return upload_route()

    @app.route('/upload/text', methods=['POST'], strict_slashes=False)
    @app.route('/upload/text/', methods=['POST'])
    def root_upload_text():
        return index_text_route()

    return app
