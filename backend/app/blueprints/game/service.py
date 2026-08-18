"""Core game logic: identity resolution, session lifecycle, guess scoring.

Kept independent of Flask request/response objects (routes.py handles cookies
and JSON) so it's unit-testable directly.
"""

from datetime import datetime, timezone

from ...extensions import db
from ...models.article import Article
from ...models.clue import Clue
from ...models.daily_challenge import DailyChallenge
from ...models.session import GameSession, GuessAttempt
from ...models.stats import UserStats
from ...lib import degrees as degrees_lib
from ...lib.mediawiki_api import MediaWikiClient
from ...lib.resolve import resolve_guess_text
from ...lib.similarity import bucket_lexical, score_lexical


class GameError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_todays_challenge() -> DailyChallenge | None:
    today = datetime.now(timezone.utc).date()
    return DailyChallenge.query.filter_by(challenge_date=today).first()


def get_or_create_session(
    daily_challenge: DailyChallenge, user_id: int | None, anon_token: str | None
) -> GameSession:
    query = GameSession.query.filter_by(daily_challenge_id=daily_challenge.id)
    if user_id:
        existing = query.filter_by(user_id=user_id).first()
    else:
        existing = query.filter_by(anon_token=anon_token).first()

    if existing:
        return existing

    session_row = GameSession(
        daily_challenge_id=daily_challenge.id,
        user_id=user_id,
        anon_token=None if user_id else anon_token,
        status="in_progress",
        clues_revealed=1,
        guesses_made=0,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(session_row)
    db.session.commit()
    return session_row


def _clue_ids_revealed(daily_challenge: DailyChallenge, clues_revealed: int) -> list[int]:
    return daily_challenge.clue_order[:clues_revealed]


def serialize_state(session_row: GameSession, daily_challenge: DailyChallenge, article: Article) -> dict:
    revealed_ids = _clue_ids_revealed(daily_challenge, session_row.clues_revealed)
    clues = Clue.query.filter(Clue.id.in_(revealed_ids)).all() if revealed_ids else []
    clues_by_id = {c.id: c for c in clues}
    ordered_clues = [
        {
            "clue_id": cid,
            "clue_type": clues_by_id[cid].clue_type,
            "clue_text": clues_by_id[cid].clue_text,
            "clue_media_url": clues_by_id[cid].clue_media_url,
        }
        for cid in revealed_ids
        if cid in clues_by_id
    ]

    guesses = [
        {
            "attempt_number": g.attempt_number,
            "raw_guess_text": g.raw_guess_text,
            "resolved_title": g.resolved_title,
            "lexical_score_bucket": g.lexical_score_bucket,
            "degrees_value": g.degrees_value,
            "degrees_capped": g.degrees_capped,
            "is_correct": g.is_correct,
        }
        for g in session_row.guess_attempts
    ]

    state = {
        "challenge_date": daily_challenge.challenge_date.isoformat(),
        "slot_pattern": article.slot_pattern,
        "clues_revealed": ordered_clues,
        "total_clues_available": len(daily_challenge.clue_order),
        "status": session_row.status,
        "guesses": guesses,
    }
    if session_row.status in ("won", "lost"):
        state["solved_answer_title"] = article.display_title
        state["summary_extract"] = article.summary_extract
    return state


def _update_user_stats(user_id: int, won: bool, attempt_number: int | None) -> None:
    stats = db.session.get(UserStats, user_id)
    if stats is None:
        stats = UserStats(user_id=user_id, win_distribution={})
        db.session.add(stats)

    stats.games_played += 1
    distribution = dict(stats.win_distribution or {})
    today = datetime.now(timezone.utc).date()

    if won:
        stats.games_won += 1
        key = str(attempt_number)
        distribution[key] = distribution.get(key, 0) + 1
        if stats.last_played_date is not None and (today - stats.last_played_date).days == 1:
            stats.current_streak += 1
        else:
            stats.current_streak = 1
        stats.max_streak = max(stats.max_streak, stats.current_streak)
    else:
        distribution["failed"] = distribution.get("failed", 0) + 1
        stats.current_streak = 0

    stats.win_distribution = distribution
    stats.last_played_date = today


def process_guess(
    session_row: GameSession,
    daily_challenge: DailyChallenge,
    article: Article,
    guess_text: str,
    client: MediaWikiClient,
    degrees_config: dict,
) -> GuessAttempt:
    if session_row.status != "in_progress":
        raise GameError("This puzzle is already finished.", status_code=409)

    guess_text = (guess_text or "").strip()
    if not guess_text:
        raise GameError("Guess text is required.")

    resolved = resolve_guess_text(client, guess_text)
    raw_score = score_lexical(guess_text, article.display_title)
    bucket = bucket_lexical(raw_score)

    is_correct = bool(resolved) and resolved["pageid"] == article.wiki_pageid

    degrees_value = None
    degrees_capped = False
    if resolved:
        result = degrees_lib.compute_degrees(
            client,
            article,
            resolved["pageid"],
            depth_cap=degrees_config["depth_cap"],
            node_cap=degrees_config["node_cap"],
            timeout_sec=degrees_config["timeout_sec"],
        )
        degrees_value = result.degrees
        degrees_capped = result.capped

    attempt_number = session_row.guesses_made + 1
    attempt = GuessAttempt(
        game_session_id=session_row.id,
        attempt_number=attempt_number,
        raw_guess_text=guess_text,
        resolved_title=resolved["title"] if resolved else None,
        resolved_pageid=resolved["pageid"] if resolved else None,
        lexical_score_bucket=bucket,
        lexical_score_raw=raw_score,
        degrees_value=degrees_value,
        degrees_capped=degrees_capped,
        is_correct=is_correct,
    )
    db.session.add(attempt)

    session_row.guesses_made = attempt_number
    total_clues = len(daily_challenge.clue_order)

    if is_correct:
        session_row.status = "won"
        session_row.solved_on_guess_number = attempt_number
        session_row.finished_at = datetime.now(timezone.utc)
    elif attempt_number >= total_clues:
        session_row.status = "lost"
        session_row.finished_at = datetime.now(timezone.utc)
    else:
        session_row.clues_revealed = min(session_row.clues_revealed + 1, total_clues)

    if session_row.status in ("won", "lost") and session_row.user_id:
        _update_user_stats(
            session_row.user_id,
            won=session_row.status == "won",
            attempt_number=session_row.solved_on_guess_number,
        )

    db.session.commit()
    return attempt
