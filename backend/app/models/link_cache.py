from datetime import datetime, timezone

from ..extensions import db


class LinkCacheNode(db.Model):
    """A same-shape neighbor of an answer article, discovered by BFS over the
    real link graph (see scripts/precompute_link_cache.py). Only nodes whose
    title normalizes (lib.slot_pattern.normalize_to_tiles) to the same total
    tile count as the answer are ever written here -- anything else could
    never be typed into the answer's fixed-length tile board, so it's not a
    useful degrees-of-Wikipedia candidate.

    node_tiles (lowercased normalize_to_tiles(node_title)) doubles as the
    guess-resolution key: backend/app/lib/degrees.py looks a submitted guess
    up directly by (answer_article_id, node_tiles) to find both the real
    article it spells out and its precomputed hop-distance, with no live API
    call needed at guess time.
    """

    __tablename__ = "link_cache_nodes"

    id = db.Column(db.Integer, primary_key=True)
    answer_article_id = db.Column(
        db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    node_pageid = db.Column(db.Integer, nullable=False)
    node_title = db.Column(db.String(255), nullable=False)
    node_tiles = db.Column(db.String(255), nullable=False)
    degree = db.Column(db.SmallInteger, nullable=False)
    discovered_via = db.Column(
        db.Enum("precompute", "live_bfs", name="link_cache_discovered_via"),
        nullable=False,
        default="precompute",
    )
    computed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("answer_article_id", "node_pageid", name="uq_link_cache_answer_node"),
        db.Index("ix_link_cache_answer_degree", "answer_article_id", "degree"),
        db.Index("ix_link_cache_node_title", "node_title"),
        db.Index("ix_link_cache_answer_tiles", "answer_article_id", "node_tiles"),
    )


class LinkCacheMeta(db.Model):
    __tablename__ = "link_cache_meta"

    answer_article_id = db.Column(
        db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    max_depth_precomputed = db.Column(db.SmallInteger, nullable=False, default=4)
    node_cap = db.Column(db.Integer, nullable=False, default=3000)
    node_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(
        db.Enum("pending", "complete", "capped", "failed", name="link_cache_status"),
        nullable=False,
        default="pending",
    )
    computed_at = db.Column(db.DateTime, nullable=True)
