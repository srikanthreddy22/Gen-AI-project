from flask import Flask, jsonify
from flask_cors import CORS
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


def _normalize_cors_origins(raw_value):
    origins = ["https://note-bot-genai.vercel.app"]
    if raw_value is None:
        for local in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            if local not in origins:
                origins.append(local)
        return origins
    if isinstance(raw_value, list):
        for item in raw_value:
            if item not in origins:
                origins.append(item)
        return origins
    sanitized = str(raw_value).strip()
    if not sanitized or sanitized == "*":
        for local in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            if local not in origins:
                origins.append(local)
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
            r"/api/*": {
                "origins": app.config.get("CORS_ORIGINS"),
            }
        },
        supports_credentials=True,
    )

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
    from .routes.upload import bp as upload_bp
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

    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'version': '1.0.0'}

    return app
