from datetime import datetime, timezone

from ..extensions import db


class TitleResolution(db.Model):
    """Global cache: free-text guess -> resolved Wikipedia article.

    Independent of any particular answer article, so it's shared across all
    guesses on all days.
    """

    __tablename__ = "title_resolutions"

    normalized_guess = db.Column(db.String(255), primary_key=True)
    resolved_pageid = db.Column(db.Integer, nullable=True)
    resolved_title = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
