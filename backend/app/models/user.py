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
    hint_mode_preference = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    theme_preference = db.Column(
        db.Enum("dark", "light", name="theme_preference"),
        nullable=False,
        default="dark",
        server_default="dark",
    )
    # --- daily-reminder push preferences -------------------------------
    # The puzzle always rolls over at 00:00 UTC; a reminder fires
    # notify_hours_before_reset hours ahead of that, so the send time is a
    # fixed UTC instant shared by every user with the same offset -- no
    # per-user timezone is stored, the frontend just renders that instant in
    # local time. See scripts/send_push_reminders.py.
    notify_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    notify_hours_before_reset = db.Column(
        db.SmallInteger, nullable=False, default=3, server_default="3"
    )
    # "incomplete": today's puzzle isn't finished (never opened, or opened
    # and still in progress). "untouched": only when they haven't started at
    # all -- a strict subset, for players who don't want nagging once they've
    # engaged. Loading the page doesn't create a session (see
    # game/service.py::get_session), so "untouched" really does mean no
    # guess or pass has been made.
    notify_trigger = db.Column(
        db.Enum("incomplete", "untouched", name="notify_trigger"),
        nullable=False,
        default="incomplete",
        server_default="incomplete",
    )
    # Guards against duplicate sends when the reminder job runs more often
    # than once a day (it runs hourly, so without this every run after the
    # target time would re-notify).
    last_notified_for_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    stats = db.relationship("UserStats", backref="user", uselist=False, cascade="all, delete-orphan")
    game_sessions = db.relationship("GameSession", backref="user")
    push_subscriptions = db.relationship(
        "PushSubscription", backref="user", cascade="all, delete-orphan"
    )
