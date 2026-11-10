from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db
from ..models import RevokedToken, User, UserProfile

bp = Blueprint("auth", __name__)


@bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")
    email = email.strip().casefold() if isinstance(email, str) else ""
    username = username.strip() if isinstance(username, str) else ""

    if not email or not username or not password:
        return jsonify({"error": "Email, username, and password are required."}), 400
    if not isinstance(password, str):
        return jsonify({"error": "Password must be a string."}), 400
    if len(email) > 255 or len(username) > 120 or len(password) > 1024:
        return jsonify({"error": "One or more fields exceed the allowed length."}), 400
    if "@" not in email:
        return jsonify({"error": "A valid email address is required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if User.query.filter((User.email == email) | (User.username == username)).first():
        return jsonify({"error": "User with that email or username already exists."}), 409

    user = User(email=email, username=username, password_hash=generate_password_hash(password))
    try:
        db.session.add(user)
        db.session.flush()
        db.session.add(UserProfile(user_id=user.id, full_name=username))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "User with that email or username already exists."}), 409
    except Exception:
        db.session.rollback()
        raise

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "message": "User registered successfully.",
        "token": token,
        "user": {"id": user.id, "email": user.email, "username": user.username},
    }), 201


@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email") or data.get("username") or ""
    password = data.get("password") or ""
    email = email.strip().casefold() if isinstance(email, str) else ""

    if not email or not password:
        return jsonify({"error": "Email/username and password are required."}), 400
    if not isinstance(password, str):
        return jsonify({"error": "Invalid credentials."}), 401

    user = User.query.filter((User.email == email) | (User.username == email)).first()
    if not user or not user.is_active or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials."}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "message": "Login successful.",
        "token": token,
        "user": {"id": user.id, "email": user.email, "username": user.username},
    })


@bp.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    profile = user.profiles
    return jsonify({
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "profile": {
            "full_name": profile.full_name if profile else "",
            "bio": profile.bio if profile else "",
            "institution": profile.institution if profile else "",
            "avatar_url": profile.avatar_url if profile else "",
        } if profile else None,
    })


@bp.route("/auth/logout", methods=["POST"])
@jwt_required()
def logout():
    claims = get_jwt()
    revoked = RevokedToken(
        jti=claims["jti"],
        user_id=get_jwt_identity(),
        expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc).replace(tzinfo=None),
    )
    try:
        db.session.add(revoked)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify({"message": "Logout successful."})


@bp.route("/auth/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    data = request.get_json(silent=True) or {}

    profile = user.profiles or UserProfile(user_id=user.id)
    profile.full_name = (data.get("full_name") or profile.full_name or "").strip()
    profile.bio = (data.get("bio") or profile.bio or "").strip()
    profile.institution = (data.get("institution") or profile.institution or "").strip()
    profile.avatar_url = (data.get("avatar_url") or profile.avatar_url or "").strip()
    if not user.profiles:
        db.session.add(profile)
    db.session.commit()
    return jsonify({"message": "Profile updated."})
