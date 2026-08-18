from datetime import datetime, timezone

from ..extensions import db


class User(db.Model):
    """Wikimedia identity only. OAuth access/refresh tokens are never persisted:
    the app only needs the user's identity, not delegated API access, so tokens
    are used transiently during the OAuth callback and discarded.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    wikimedia_sub = db.Column(db.String(64), nullable=False, unique=True)
    wikimedia_username = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    stats = db.relationship("UserStats", backref="user", uselist=False, cascade="all, delete-orphan")
    game_sessions = db.relationship("GameSession", backref="user")
