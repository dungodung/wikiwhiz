#!/usr/bin/env python3
"""Insert a clue for an article, enforcing a hard title-leak guard.

Usage:
  db_add_clue.py --article-id 12 --type infobox_fact \
      --text "Born in the German Empire." [--reveal-rank-hint 3] \
      [--media-url URL] [--payload-json '{"k":"v"}']

Independent of whatever self-check Claude did while drafting the clue text,
this script refuses (exit 1, nothing written) to insert any clue whose text
contains the article's title or display title as a case-insensitive
substring. On failure, redraft the clue text and try again.

If the article is already scheduled, the challenge's frozen clue_order is
recomputed to include the new clue -- otherwise the clue would exist in the
database but be unreachable in play. See
backend/app/lib/scheduling.py::sync_clue_order.
"""

import argparse
import json
import sys
from datetime import date

from _db import session_scope

from backend.app.lib.clue_guard import leaks_title
from backend.app.lib.scheduling import sync_clue_order
from backend.app.models.article import Article
from backend.app.models.clue import CLUE_TYPES, Clue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-id", type=int, required=True)
    parser.add_argument("--type", required=True, choices=CLUE_TYPES)
    parser.add_argument("--text", required=True)
    parser.add_argument("--reveal-rank-hint", type=int, default=3)
    parser.add_argument("--media-url")
    parser.add_argument("--payload-json")
    args = parser.parse_args()

    with session_scope() as session:
        article = session.get(Article, args.article_id)
        if not article:
            print(f"ERROR: no article with id {args.article_id}", file=sys.stderr)
            return 1

        if leaks_title(args.text, article):
            print(
                f"REJECTED: clue text leaks the article title "
                f"({article.display_title!r}). Redraft and retry.",
                file=sys.stderr,
            )
            return 1

        payload = json.loads(args.payload_json) if args.payload_json else None

        clue = Clue(
            article_id=article.id,
            clue_type=args.type,
            reveal_rank_hint=args.reveal_rank_hint,
            clue_text=args.text,
            clue_media_url=args.media_url,
            clue_payload=payload,
            is_title_leaking=False,
        )
        session.add(clue)
        session.flush()
        print(f"OK: clue_id={clue.id}")

        # Keep the frozen reveal order in step with the clue set -- without
        # this, a clue added after the article was scheduled is invisible to
        # players forever (see sync_clue_order's docstring).
        new_order = sync_clue_order(session, article)
        if new_order is not None:
            print(f"OK: clue_order refreshed -> {len(new_order)} clues")
            challenge_date = article.daily_challenge.challenge_date
            if challenge_date <= date.today():
                print(
                    f"WARNING: {challenge_date.isoformat()} is today or in the past -- "
                    f"this changed the reveal order of a puzzle players may already have seen.",
                    file=sys.stderr,
                )
        return 0


if __name__ == "__main__":
    sys.exit(main())
