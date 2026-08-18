#!/usr/bin/env python3
"""Schedule a `ready` article onto the next open UTC daily-challenge slot.

Usage:
  db_schedule_challenge.py --article-id 12 --next-available

Finds the first UTC date after MAX(challenge_date) with no existing row (or
today, if the schedule is currently empty), computes a seeded clue reveal
order (seeded by the new daily_challenges.id, so it's stable forever once
assigned), and inserts inside a transaction. Core logic lives in
backend/app/lib/scheduling.py, shared with the admin API's manual scheduling
endpoint so both paths behave identically.
"""

import argparse
import sys

from _db import get_session

from backend.app.lib.scheduling import SchedulingError, schedule_article
from backend.app.models.article import Article


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-id", type=int, required=True)
    parser.add_argument(
        "--next-available", action="store_true", help="required flag, documents intent"
    )
    args = parser.parse_args()

    session = get_session()
    try:
        article = session.get(Article, args.article_id)
        if not article:
            print(f"ERROR: no article with id {args.article_id}", file=sys.stderr)
            return 1
        if article.status != "ready":
            print(f"ERROR: article {article.id} has status {article.status!r}, expected 'ready'", file=sys.stderr)
            return 1

        challenge = schedule_article(session, article)
        session.commit()
        print(f"OK: article_id={article.id} scheduled for {challenge.challenge_date.isoformat()}")
        return 0
    except SchedulingError as exc:
        session.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
