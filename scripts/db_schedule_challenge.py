#!/usr/bin/env python3
"""Schedule a `ready` article onto the next open UTC daily-challenge slot.

Usage:
  db_schedule_challenge.py --article-id 12 --next-available

Finds the first UTC date after MAX(challenge_date) with no existing row (or
today, if the schedule is currently empty), computes a seeded clue reveal
order (seeded by the new daily_challenges.id, so it's stable forever once
assigned), and inserts inside a transaction. daily_challenges.challenge_date
is UNIQUE, so a collision (e.g. a concurrent invocation) raises IntegrityError
and this script just retries the next day -- scheduling is safe by
construction, no locking needed.
"""

import argparse
import sys
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

from _db import get_session

from backend.app.lib.clue_selection import compute_clue_order
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge

MAX_RETRY_DAYS = 1000


def _next_candidate_date(session) -> date:
    latest = session.query(DailyChallenge.challenge_date).order_by(
        DailyChallenge.challenge_date.desc()
    ).first()
    if latest is None:
        return date.today()
    return latest[0] + timedelta(days=1)


def schedule(session, article: Article) -> DailyChallenge:
    clue_rows = [
        {"id": c.id, "reveal_rank_hint": c.reveal_rank_hint}
        for c in session.query(Clue).filter_by(article_id=article.id, is_title_leaking=False).all()
    ]
    if len(clue_rows) < 5:
        raise ValueError(f"article {article.id} has only {len(clue_rows)} usable clues, needs >= 5")

    candidate_date = _next_candidate_date(session)

    for _ in range(MAX_RETRY_DAYS):
        challenge = DailyChallenge(challenge_date=candidate_date, article_id=article.id, clue_order=[])
        session.add(challenge)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            candidate_date += timedelta(days=1)
            continue

        challenge.clue_order = compute_clue_order(clue_rows, seed=challenge.id)
        article.status = "scheduled"
        session.commit()
        return challenge

    raise RuntimeError("could not find an open challenge_date slot")


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

        challenge = schedule(session, article)
        print(f"OK: article_id={article.id} scheduled for {challenge.challenge_date.isoformat()}")
        return 0
    except (ValueError, RuntimeError) as exc:
        session.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
