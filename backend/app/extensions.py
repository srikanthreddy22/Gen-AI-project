from __future__ import annotations

from typing import Any

try:
    from flask_sqlalchemy import SQLAlchemy
    from flask_migrate import Migrate
    from flask_jwt_extended import JWTManager
except Exception:  # pragma: no cover - optional dependencies may be absent
    SQLAlchemy = None
    Migrate = None
    JWTManager = None


if SQLAlchemy is not None:
    db = SQLAlchemy()
    migrate = Migrate()
    jwt = JWTManager()
else:  # Graceful fallback when optional infrastructure dependencies are not installed.
    class _MissingDb:
        def __getattr__(self, name: str) -> Any:
            if name in {"init_app", "session", "Model", "Column", "relationship", "ForeignKey"}:
                return None
            return None

    db = _MissingDb()
    migrate = _MissingDb()
    jwt = _MissingDb()
