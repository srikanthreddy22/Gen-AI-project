import uuid

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import User


def issue_auth_headers(app, username=None):
    username = username or f"learner-{uuid.uuid4().hex[:8]}"
    with app.app_context():
        user = User(
            email=f"{username}@example.test",
            username=username,
            password_hash="test-hash",
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=user.id)
        return {"Authorization": f"Bearer {token}"}, user.id
