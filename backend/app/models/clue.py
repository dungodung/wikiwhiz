from datetime import datetime, timezone

from ..extensions import db

CLUE_TYPES = (
    "commons_image",
    "dyk_or_notable_fact",
    "wikidata_fact",
    "infobox_fact",
    "categories",
    "etymology",
    "wikisource_excerpt",
    "wikivoyage_fact",
    "pageviews",
    "top_citation",
    "incoming_links",
    "long_section_title",
    "creation_year",
    "langlinks_count",
)


class Clue(db.Model):
    __tablename__ = "clues"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(
        db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    clue_type = db.Column(db.Enum(*CLUE_TYPES, name="clue_type"), nullable=False)
    reveal_rank_hint = db.Column(db.SmallInteger, nullable=False, default=3)
    clue_text = db.Column(db.Text, nullable=False)
    clue_media_url = db.Column(db.String(1024), nullable=True)
    clue_payload = db.Column(db.JSON, nullable=True)
    is_title_leaking = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.Index("ix_clues_article_id", "article_id"),)
