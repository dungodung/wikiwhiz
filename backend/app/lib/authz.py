"""Authorization helpers for admin-only routes."""

from functools import wraps

from flask import jsonify, session

from ..extensions import db
from ..models.user import User


def current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def require_admin(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "not_authenticated"}), 401
        if not user.is_admin:
            return jsonify({"error": "admin_required"}), 403
        return view_func(*args, **kwargs)

    return wrapped
