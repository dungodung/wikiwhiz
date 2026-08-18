from datetime import datetime, timezone

from ..extensions import db


class DailyChallenge(db.Model):
    __tablename__ = "daily_challenges"

    id = db.Column(db.Integer, primary_key=True)
    challenge_date = db.Column(db.Date, nullable=False, unique=True)
    article_id = db.Column(
        db.Integer, db.ForeignKey("articles.id"), nullable=False, unique=True
    )
    # Frozen, ordered list of clue ids, computed once at scheduling time.
    # Request handlers only ever index into this — no per-request randomization.
    clue_order = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    game_sessions = db.relationship("GameSession", backref="daily_challenge")

    __table_args__ = (db.Index("ix_daily_challenges_date", "challenge_date"),)
