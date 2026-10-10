from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import sys
import os

# Load .env from backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path, override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

    CORS(app)

    from .routes.summarize import bp as summarize_bp
    from .routes.flashcards import bp as flashcards_bp
    from .routes.quiz import bp as quiz_bp
    from .routes.upload import bp as upload_bp
    from .routes.export import bp as export_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(summarize_bp, url_prefix='/api')
    app.register_blueprint(flashcards_bp, url_prefix='/api')
    app.register_blueprint(quiz_bp, url_prefix='/api')
    app.register_blueprint(upload_bp, url_prefix='/api')
    app.register_blueprint(export_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')

    @app.route('/')
    def home():
        return jsonify({"status": "Backend Running Successfully"})

    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'version': '1.0.0'}

    return app
