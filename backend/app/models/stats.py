from datetime import datetime, timezone

from ..extensions import db


class UserStats(db.Model):
    __tablename__ = "user_stats"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    games_played = db.Column(db.Integer, nullable=False, default=0)
    games_won = db.Column(db.Integer, nullable=False, default=0)
    # e.g. {"1": 2, "2": 5, "3": 1, "failed": 1} -- JSON avoids a migration if
    # the clue-count range (5-7) ever changes.
    win_distribution = db.Column(db.JSON, nullable=False, default=dict)
    current_streak = db.Column(db.Integer, nullable=False, default=0)
    max_streak = db.Column(db.Integer, nullable=False, default=0)
    last_played_date = db.Column(db.Date, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
