from datetime import datetime, timezone

from ..extensions import db


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    wiki_title = db.Column(db.String(255), nullable=False, unique=True)
    wiki_pageid = db.Column(db.Integer, nullable=False, unique=True)
    display_title = db.Column(db.String(255), nullable=False)
    slot_pattern = db.Column(db.JSON, nullable=False)
    summary_extract = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum("draft", "ready", "scheduled", "retired", name="article_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    difficulty_tier = db.Column(db.SmallInteger, nullable=True)
    source_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    clues = db.relationship("Clue", backref="article", cascade="all, delete-orphan")
    daily_challenge = db.relationship("DailyChallenge", backref="article", uselist=False)

    __table_args__ = (db.Index("ix_articles_status", "status"),)
