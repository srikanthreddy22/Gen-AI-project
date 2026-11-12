import os
import warnings
from datetime import timedelta

from sqlalchemy.engine import make_url
from dotenv import load_dotenv

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_backend_dir, ".env"))


def _sanitize_cors_origins(raw_value: str | None) -> str:
    if raw_value is None:
        return "*"
    sanitized = raw_value.strip()
    if not sanitized:
        return "*"
    if sanitized.lower().startswith("cors_origins="):
        sanitized = sanitized.split("=", 1)[1].strip()
    if not sanitized:
        return "*"
    if sanitized.startswith("[") and sanitized.endswith("]"):
        sanitized = sanitized[1:-1]
    origins = [item.strip().rstrip("/") for item in sanitized.split(",") if item.strip()]
    return ",".join(origins) if origins else "*"


class Config:
    FLASK_APP = os.getenv("FLASK_APP", "run.py")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    PORT = int(os.getenv("PORT", "5000"))

    SECRET_KEY = os.getenv("SECRET_KEY", "notebot-development-secret-change-before-deploy")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "12")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30")))
    _database_url = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:root@localhost:3306/notebot",
    )
    _parsed_database_url = make_url(_database_url)
    if _parsed_database_url.drivername == "mysql":
        _parsed_database_url = _parsed_database_url.set(drivername="mysql+pymysql")

    _database_query = dict(_parsed_database_url.query)
    _ssl_mode = str(
        _database_query.pop("ssl-mode", _database_query.pop("ssl_mode", ""))
    ).upper()
    _parsed_database_url = _parsed_database_url.set(query=_database_query)
    SQLALCHEMY_DATABASE_URI = _parsed_database_url.render_as_string(hide_password=False)

    _mysql_connect_args = {}
    if _parsed_database_url.drivername.startswith("mysql"):
        if _ssl_mode in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}:
            _mysql_connect_args["ssl"] = {}
        _db_ssl_ca = os.getenv("DB_SSL_CA", "").strip()
        if _db_ssl_ca:
            _resolved_ssl_ca = _db_ssl_ca
            if not os.path.isabs(_resolved_ssl_ca):
                _resolved_ssl_ca = os.path.join(_backend_dir, _resolved_ssl_ca)
            _resolved_ssl_ca = os.path.abspath(_resolved_ssl_ca)
            if os.path.isfile(_resolved_ssl_ca):
                _mysql_connect_args["ssl_ca"] = _resolved_ssl_ca
                _mysql_connect_args["ssl_verify_cert"] = True
                _mysql_connect_args["ssl_verify_identity"] = True
            else:
                warnings.warn(
                    "DB_SSL_CA points to a missing file; MySQL TLS will be encrypted "
                    "without CA/hostname verification.",
                    RuntimeWarning,
                    stacklevel=2,
                )
        if _ssl_mode in {"VERIFY_CA", "VERIFY_IDENTITY"} and "ssl_ca" not in _mysql_connect_args:
            raise RuntimeError(f"DB_SSL_CA is required for MySQL ssl-mode={_ssl_mode}")

    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv(
        "SQLALCHEMY_TRACK_MODIFICATIONS",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "connect_args": _mysql_connect_args,
    }
    AUTO_CREATE_SCHEMA = os.getenv("NOTEBOT_AUTO_CREATE_SCHEMA", "false").strip().lower() in {
        "1", "true", "yes",
    }
    CORS_ORIGINS = _sanitize_cors_origins(os.getenv("CORS_ORIGINS", "*"))
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
    GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    GEMINI_EMBEDDING_DIMENSION = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", "3072"))
    LOCAL_EMBEDDING_MODEL = os.getenv(
        "LOCAL_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    LOCAL_EMBEDDING_DEVICE = os.getenv("LOCAL_EMBEDDING_DEVICE", "cpu")
    ENABLE_LOCAL_EMBEDDINGS = os.getenv("ENABLE_LOCAL_EMBEDDINGS", "false").strip().lower() in {
        "1", "true", "yes",
    }
    MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.35"))
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads"),
    )
    CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", os.path.join(os.getcwd(), "data", "chroma"))
    CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
    TOP_K = RAG_TOP_K
    RAG_DEBUG = os.getenv("RAG_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
    LEGACY_VECTOR_STORE_PATH = os.getenv("LEGACY_VECTOR_STORE_PATH")
    DISABLE_LEGACY_VECTOR_MIGRATION = os.getenv(
        "NOTEBOT_DISABLE_LEGACY_VECTOR_MIGRATION",
        "",
    ).strip().lower() in {"1", "true", "yes"}
