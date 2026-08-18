"""Shared daily-challenge scheduling logic, used by both
scripts/db_schedule_challenge.py and the admin API so both paths schedule
articles identically (same seeded clue-order computation, same collision
handling on the UNIQUE(challenge_date) constraint).
"""

from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

from .clue_selection import compute_clue_order
from ..models.article import Article
from ..models.clue import Clue
from ..models.daily_challenge import DailyChallenge

MAX_RETRY_DAYS = 1000


class SchedulingError(Exception):
    pass


def next_open_date(session, after: date | None = None) -> date:
    query = session.query(DailyChallenge.challenge_date).order_by(
        DailyChallenge.challenge_date.desc()
    )
    latest = query.first()
    candidate = (after or date.today())
    if latest is not None and latest[0] >= candidate:
        candidate = latest[0] + timedelta(days=1)
    return candidate


def schedule_article(session, article: Article, on_date: date | None = None) -> DailyChallenge:
    """Schedules `article` onto `on_date` if given (must be free), otherwise
    the next open date after today. Raises SchedulingError on failure.
    """
    clue_rows = [
        {"id": c.id, "reveal_rank_hint": c.reveal_rank_hint}
        for c in session.query(Clue).filter_by(article_id=article.id, is_title_leaking=False).all()
    ]
    if len(clue_rows) < 5:
        raise SchedulingError(f"article {article.id} has only {len(clue_rows)} usable clues, needs >= 5")

    if on_date is not None:
        challenge = DailyChallenge(challenge_date=on_date, article_id=article.id, clue_order=[])
        session.add(challenge)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise SchedulingError(f"{on_date.isoformat()} is already scheduled") from exc
        challenge.clue_order = compute_clue_order(clue_rows, seed=challenge.id)
        article.status = "scheduled"
        return challenge

    candidate_date = next_open_date(session)
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
        return challenge

    raise SchedulingError("could not find an open challenge_date slot")


def unschedule_article(session, challenge: DailyChallenge) -> None:
    """Removes a future scheduling and reverts the article to 'ready'. Caller
    must have already verified challenge.challenge_date is in the future.
    """
    article = session.get(Article, challenge.article_id)
    session.delete(challenge)
    session.flush()
    if article:
        article.status = "ready"
