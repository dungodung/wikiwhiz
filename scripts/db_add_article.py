#!/usr/bin/env python3
"""Insert a new candidate article (status=draft), or promote one to ready.

Usage:
  db_add_article.py --title "Albert Einstein" --pageid 736 \
      --display-title "Albert Einstein" [--summary "..."] [--notes "..."]
  db_add_article.py --set-status ready --article-id 12

Promoting to `ready` is gated: the article must have >=5 clues, none of them
flagged is_title_leaking, before the status change is allowed.
"""

import argparse
import sys

from _db import session_scope

from backend.app.lib.slot_pattern import tokenize_title_to_slots
from backend.app.models.article import Article
from backend.app.models.clue import Clue

MIN_CLUES_FOR_READY = 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", help="Exact enwiki article title")
    parser.add_argument("--pageid", type=int)
    parser.add_argument("--display-title", help="Title as shown to players (usually same as --title)")
    parser.add_argument("--summary")
    parser.add_argument("--notes")
    parser.add_argument("--set-status", choices=["draft", "ready", "retired"])
    parser.add_argument("--article-id", type=int)
    args = parser.parse_args()

    with session_scope() as session:
        if args.set_status:
            if not args.article_id:
                print("ERROR: --article-id required with --set-status", file=sys.stderr)
                return 1
            article = session.get(Article, args.article_id)
            if not article:
                print(f"ERROR: no article with id {args.article_id}", file=sys.stderr)
                return 1

            if args.set_status == "ready":
                clue_count = (
                    session.query(Clue)
                    .filter_by(article_id=article.id, is_title_leaking=False)
                    .count()
                )
                if clue_count < MIN_CLUES_FOR_READY:
                    print(
                        f"ERROR: article {article.id} has only {clue_count} non-leaking "
                        f"clues, needs >= {MIN_CLUES_FOR_READY} before it can go 'ready'",
                        file=sys.stderr,
                    )
                    return 1

            article.status = args.set_status
            print(f"OK: article {article.id} status -> {args.set_status}")
            return 0

        if not (args.title and args.pageid and args.display_title):
            print("ERROR: --title, --pageid, --display-title are required to add an article", file=sys.stderr)
            return 1

        article = Article(
            wiki_title=args.title,
            wiki_pageid=args.pageid,
            display_title=args.display_title,
            slot_pattern=tokenize_title_to_slots(args.display_title),
            summary_extract=args.summary,
            source_notes=args.notes,
            status="draft",
        )
        session.add(article)
        session.flush()
        print(f"OK: article_id={article.id}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
