from datetime import datetime, timezone

from ..extensions import db


class PushSubscription(db.Model):
    """One Web Push endpoint, i.e. one browser on one device. A user can hold
    several (phone + laptop), so reminders fan out to all of them and the
    notification settings themselves live on User, not here.

    endpoint/p256dh/auth are exactly what the browser's PushSubscription
    hands back; pywebpush wants them in that shape, so they're stored
    verbatim rather than normalized. The endpoint is the identity of a
    subscription -- it's what the push service routes on, and what a
    re-subscribe returns unchanged -- hence the unique constraint, which
    makes re-subscribing an idempotent upsert instead of piling up
    duplicate rows for the same browser.

    These rows are disposable: a push service returns 404/410 once an
    endpoint is permanently gone (browser uninstalled, subscription revoked,
    user cleared site data), and lib/push.py deletes the row when it sees
    that. Nothing here is worth preserving against the user's wishes -- the
    settings modal's off switch deletes the row outright.
    """

    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Push endpoints are long URLs (FCM's run ~200 chars, but the spec sets
    # no limit); 500 leaves headroom while staying inside MySQL's index-size
    # limit for a unique key on utf8mb4.
    endpoint = db.Column(db.String(500), nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_sent_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.Index("ix_push_subscriptions_user", "user_id"),)

    def to_webpush_info(self) -> dict:
        """The subscription_info shape pywebpush expects."""
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }
