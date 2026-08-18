#!/usr/bin/env python3
"""Export articles/clues/daily_challenges/link_cache rows added locally since
a watermark article id, as SQL INSERT statements, for promotion to production.

Usage:
  db_export_pool.py --since-id 42 > pool_export.sql

Applied to ToolsDB by scripts/sync_pool_to_prod.sh over an SSH tunnel. Content
is authored locally (where Claude Code runs) and reviewed before being synced
this way, rather than the content-authoring skill running against production
directly -- see docs/deployment-toolforge.md.
"""

import argparse
import json
import sys

from _db import session_scope

from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge
from backend.app.models.link_cache import LinkCacheMeta, LinkCacheNode


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _insert_statements(table: str, columns: list[str], rows: list[dict]) -> list[str]:
    statements = []
    for row in rows:
        values = ", ".join(_sql_literal(row[col]) for col in columns)
        cols = ", ".join(columns)
        statements.append(f"INSERT IGNORE INTO {table} ({cols}) VALUES ({values});")
    return statements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-id", type=int, required=True, help="Export articles with id > this watermark")
    args = parser.parse_args()

    with session_scope() as session:
        articles = session.query(Article).filter(Article.id > args.since_id).all()
        if not articles:
            print("-- nothing to export", file=sys.stderr)
            return 0

        article_ids = [a.id for a in articles]

        print(f"-- WikiWhiz pool export: {len(articles)} articles since id={args.since_id}")
        print("START TRANSACTION;")

        for stmt in _insert_statements(
            "articles",
            ["id", "wiki_title", "wiki_pageid", "display_title", "slot_pattern",
             "summary_extract", "status", "difficulty_tier", "source_notes",
             "created_at", "updated_at"],
            [
                {
                    "id": a.id, "wiki_title": a.wiki_title, "wiki_pageid": a.wiki_pageid,
                    "display_title": a.display_title,
                    "slot_pattern": json.dumps(a.slot_pattern),
                    "summary_extract": a.summary_extract, "status": a.status,
                    "difficulty_tier": a.difficulty_tier, "source_notes": a.source_notes,
                    "created_at": a.created_at, "updated_at": a.updated_at,
                }
                for a in articles
            ],
        ):
            print(stmt)

        clues = session.query(Clue).filter(Clue.article_id.in_(article_ids)).all()
        for stmt in _insert_statements(
            "clues",
            ["id", "article_id", "clue_type", "reveal_rank_hint", "clue_text",
             "clue_media_url", "clue_payload", "is_title_leaking", "created_at"],
            [
                {
                    "id": c.id, "article_id": c.article_id, "clue_type": c.clue_type,
                    "reveal_rank_hint": c.reveal_rank_hint, "clue_text": c.clue_text,
                    "clue_media_url": c.clue_media_url,
                    "clue_payload": json.dumps(c.clue_payload) if c.clue_payload else None,
                    "is_title_leaking": c.is_title_leaking, "created_at": c.created_at,
                }
                for c in clues
            ],
        ):
            print(stmt)

        link_nodes = session.query(LinkCacheNode).filter(
            LinkCacheNode.answer_article_id.in_(article_ids)
        ).all()
        for stmt in _insert_statements(
            "link_cache_nodes",
            ["id", "answer_article_id", "node_pageid", "node_title", "degree",
             "discovered_via", "computed_at"],
            [
                {
                    "id": n.id, "answer_article_id": n.answer_article_id,
                    "node_pageid": n.node_pageid, "node_title": n.node_title,
                    "degree": n.degree, "discovered_via": n.discovered_via,
                    "computed_at": n.computed_at,
                }
                for n in link_nodes
            ],
        ):
            print(stmt)

        link_meta = session.query(LinkCacheMeta).filter(
            LinkCacheMeta.answer_article_id.in_(article_ids)
        ).all()
        for stmt in _insert_statements(
            "link_cache_meta",
            ["answer_article_id", "max_depth_precomputed", "node_cap", "node_count",
             "status", "computed_at"],
            [
                {
                    "answer_article_id": m.answer_article_id,
                    "max_depth_precomputed": m.max_depth_precomputed,
                    "node_cap": m.node_cap, "node_count": m.node_count,
                    "status": m.status, "computed_at": m.computed_at,
                }
                for m in link_meta
            ],
        ):
            print(stmt)

        challenges = session.query(DailyChallenge).filter(
            DailyChallenge.article_id.in_(article_ids)
        ).all()
        for stmt in _insert_statements(
            "daily_challenges",
            ["id", "challenge_date", "article_id", "clue_order", "created_at"],
            [
                {
                    "id": d.id, "challenge_date": d.challenge_date, "article_id": d.article_id,
                    "clue_order": json.dumps(d.clue_order), "created_at": d.created_at,
                }
                for d in challenges
            ],
        ):
            print(stmt)

        print("COMMIT;")
        print(f"-- watermark: last exported article id = {max(article_ids)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
