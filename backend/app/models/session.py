from datetime import datetime, timezone

from ..extensions import db


class GameSession(db.Model):
    __tablename__ = "game_sessions"

    id = db.Column(db.Integer, primary_key=True)
    daily_challenge_id = db.Column(
        db.Integer, db.ForeignKey("daily_challenges.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    anon_token = db.Column(db.String(36), nullable=True)
    status = db.Column(
        db.Enum("in_progress", "won", "lost", name="game_session_status"),
        nullable=False,
        default="in_progress",
    )
    clues_revealed = db.Column(db.SmallInteger, nullable=False, default=1)
    guesses_made = db.Column(db.SmallInteger, nullable=False, default=0)
    solved_on_guess_number = db.Column(db.SmallInteger, nullable=True)
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)

    guess_attempts = db.relationship(
        "GuessAttempt", backref="game_session", cascade="all, delete-orphan",
        order_by="GuessAttempt.attempt_number",
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "daily_challenge_id", name="uq_session_user_challenge"),
        db.Index("ix_sessions_anon_challenge", "anon_token", "daily_challenge_id"),
        db.Index("ix_sessions_challenge", "daily_challenge_id"),
    )


class GuessAttempt(db.Model):
    __tablename__ = "guess_attempts"

    id = db.Column(db.Integer, primary_key=True)
    game_session_id = db.Column(
        db.Integer, db.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number = db.Column(db.SmallInteger, nullable=False)
    raw_guess_text = db.Column(db.String(255), nullable=False)
    resolved_title = db.Column(db.String(255), nullable=True)
    resolved_pageid = db.Column(db.Integer, nullable=True)
    lexical_score_bucket = db.Column(db.SmallInteger, nullable=False)
    lexical_score_raw = db.Column(db.Numeric(5, 4), nullable=False)
    degrees_value = db.Column(db.SmallInteger, nullable=True)
    degrees_capped = db.Column(db.Boolean, nullable=False, default=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.Index("ix_guess_attempts_session", "game_session_id"),)
