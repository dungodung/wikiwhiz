"""Core game logic: identity resolution, session lifecycle, guess scoring.

Kept independent of Flask request/response objects (routes.py handles cookies
and JSON) so it's unit-testable directly.
"""

import logging
import threading
from datetime import date as date_cls
from datetime import datetime, timezone

from flask import current_app

from ...extensions import db
from ...models.article import Article
from ...models.clue import Clue
from ...models.daily_challenge import DailyChallenge
from ...models.session import GameSession, GuessAttempt
from ...models.stats import UserStats
from ...lib import degrees as degrees_lib
from ...lib import hint_search
from ...lib.mediawiki_api import MediaWikiClient
from ...lib.similarity import bucket_lexical, score_lexical
from ...lib.slot_pattern import KEPT_PUNCTUATION, normalize_to_tiles

logger = logging.getLogger(__name__)


class GameError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def today_utc() -> date_cls:
    return datetime.now(timezone.utc).date()


def get_challenge_for_date(target_date: date_cls) -> DailyChallenge | None:
    """Only ever returns challenges for today or the past -- a future date is
    not yet revealed to players (admins browse future schedule via the admin
    API instead, see blueprints/admin/routes.py).
    """
    if target_date > today_utc():
        return None
    return DailyChallenge.query.filter_by(challenge_date=target_date).first()


def get_todays_challenge() -> DailyChallenge | None:
    return get_challenge_for_date(today_utc())


def list_archive(user_id: int | None, anon_token: str | None) -> list[dict]:
    """Past + today's challenges with this identity's status, for the
    calendar picker. Does not include future (unscheduled-to-players) dates.
    """
    challenges = (
        DailyChallenge.query.filter(DailyChallenge.challenge_date <= today_utc())
        .order_by(DailyChallenge.challenge_date.desc())
        .all()
    )
    if not challenges:
        return []

    challenge_ids = [c.id for c in challenges]
    query = GameSession.query.filter(GameSession.daily_challenge_id.in_(challenge_ids))
    sessions = query.filter_by(user_id=user_id).all() if user_id else query.filter_by(anon_token=anon_token).all()
    session_by_challenge = {s.daily_challenge_id: s for s in sessions}

    return [
        {
            "challenge_date": c.challenge_date.isoformat(),
            "is_today": c.challenge_date == today_utc(),
            "status": session_by_challenge[c.id].status if c.id in session_by_challenge else "not_started",
        }
        for c in challenges
    ]


def get_session(daily_challenge: DailyChallenge, user_id: int | None, anon_token: str | None) -> GameSession | None:
    """Read-only lookup -- never creates a row. Just viewing a puzzle
    shouldn't write to the database; a GameSession is only ever created when
    the player actually submits a guess (see get_or_create_session), so
    idle visits (no play at all) leave no trace.
    """
    query = GameSession.query.filter_by(daily_challenge_id=daily_challenge.id)
    if user_id:
        return query.filter_by(user_id=user_id).first()
    return query.filter_by(anon_token=anon_token).first()


def get_or_create_session(
    daily_challenge: DailyChallenge, user_id: int | None, anon_token: str | None
) -> GameSession:
    existing = get_session(daily_challenge, user_id, anon_token)
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


def serialize_state(session_row: GameSession | None, daily_challenge: DailyChallenge, article: Article) -> dict:
    """session_row is None for a puzzle the player hasn't made a guess on
    yet (see get_session) -- that's rendered as the same fresh starting
    state get_or_create_session would produce (first clue only, no
    guesses), just without a database row backing it.
    """
    clues_revealed = session_row.clues_revealed if session_row else 1
    status = session_row.status if session_row else "in_progress"
    guess_attempts = session_row.guess_attempts if session_row else []

    revealed_ids = _clue_ids_revealed(daily_challenge, clues_revealed)
    all_clue_ids = revealed_ids if status != "won" else daily_challenge.clue_order
    clues = Clue.query.filter(Clue.id.in_(all_clue_ids)).all() if all_clue_ids else []
    clues_by_id = {c.id: c for c in clues}

    def _clue_dicts(clue_ids: list[int]) -> list[dict]:
        return [
            {
                "clue_id": cid,
                "clue_type": clues_by_id[cid].clue_type,
                "clue_text": clues_by_id[cid].clue_text,
                "clue_media_url": clues_by_id[cid].clue_media_url,
            }
            for cid in clue_ids
            if cid in clues_by_id
        ]

    ordered_clues = _clue_dicts(revealed_ids)

    guesses = [
        {
            "attempt_number": g.attempt_number,
            "raw_guess_text": g.raw_guess_text,
            "resolved_title": g.resolved_title,
            "lexical_score_bucket": g.lexical_score_bucket,
            "degrees_value": g.degrees_value,
            "degrees_capped": g.degrees_capped,
            "degrees_pending": g.degrees_pending,
            "is_correct": g.is_correct,
        }
        for g in guess_attempts
    ]

    state = {
        "challenge_date": daily_challenge.challenge_date.isoformat(),
        "is_today": daily_challenge.challenge_date == today_utc(),
        "slot_pattern": article.slot_pattern,
        "clues_revealed": ordered_clues,
        "total_clues_available": len(daily_challenge.clue_order),
        "status": status,
        "guesses": guesses,
    }
    if status in ("won", "lost"):
        state["solved_answer_title"] = article.display_title
        state["solved_answer_tiles"] = normalize_to_tiles(article.display_title)
        state["summary_extract"] = article.summary_extract
    if status == "won":
        # Only once the puzzle is solved -- an in-progress or lost game
        # never gets clues it hasn't earned, since that's the whole point
        # of the reveal-on-wrong-guess mechanic. Shown dimmed client-side so
        # it's clear these were never used as guessing help.
        state["remaining_clues"] = _clue_dicts(daily_challenge.clue_order[clues_revealed:])
    return state


def _update_user_stats(user_id: int, won: bool, attempt_number: int | None) -> None:
    stats = db.session.get(UserStats, user_id)
    if stats is None:
        # Column defaults (default=0) only apply at flush/insert time, not on
        # the freshly-constructed Python object -- set them explicitly here
        # since we mutate (+=) them immediately, before any flush happens.
        stats = UserStats(
            user_id=user_id,
            games_played=0,
            games_won=0,
            win_distribution={},
            current_streak=0,
            max_streak=0,
        )
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


def check_guess_shape(article: Article, guess_tiles: str) -> None:
    """A guess is entered by filling the article's tile board directly, so it
    must already be the right length. Nothing is pre-revealed -- spaces,
    dashes, commas, and parentheses are guessable tiles just like letters,
    not fixed positions -- so the only server-side check left is length and
    that every character is one the game could ever actually use.
    """
    if len(guess_tiles) != len(article.slot_pattern):
        raise GameError("Guess must fill every tile.", status_code=400)
    for ch in guess_tiles:
        if not (ch.isalpha() or ch in KEPT_PUNCTUATION):
            raise GameError("Tiles must be filled with letters or valid punctuation.", status_code=400)


class _WrongGuessResolution:
    """Everything process_guess needs to know about a wrong guess *before*
    the (possibly slow) live BFS is attempted -- degrees are resolved
    separately, in the background, if `needs_live_bfs` is set. See
    _spawn_live_degrees_computation.
    """

    def __init__(
        self,
        pageid: int | None,
        title: str | None,
        degrees_value: int | None,
        degrees_capped: bool,
        needs_live_bfs: bool,
    ):
        self.pageid = pageid
        self.title = title
        self.degrees_value = degrees_value
        self.degrees_capped = degrees_capped
        self.needs_live_bfs = needs_live_bfs


def _resolve_wrong_guess(article: Article, guess_tiles: str, client: MediaWikiClient) -> _WrongGuessResolution:
    """A wrong guess only counts as an attempt if it spells a real enwiki
    article -- checked cheaply first against the precomputed same-shape
    neighbor cache (lib/degrees.py), then, on a cache miss, against a live
    best-effort search (lib/hint_search.py::verify_real_article). Raises on a
    confirmed non-article; on a live search failure it degrades gracefully
    (accepts the guess, just without a resolved title or degrees value)
    rather than blocking play over a transient network issue.

    A guess confirmed real but still missing from the cache (common -- the
    precompute only covers a bounded neighborhood around the answer) still
    doesn't get a live BFS *here* -- that can take anywhere from a couple of
    seconds to 20+ for two hub-like articles, and the guess itself (right or
    wrong, and whatever real article it resolves to) shouldn't wait on it.
    `needs_live_bfs=True` tells the caller to accept the guess now and kick
    the actual BFS off in the background (see _spawn_live_degrees_computation).
    """
    resolved = degrees_lib.resolve_and_score_guess(article.id, guess_tiles)
    if resolved is not None:
        return _WrongGuessResolution(
            pageid=resolved.pageid,
            title=resolved.title,
            degrees_value=resolved.degrees_result.degrees,
            degrees_capped=resolved.degrees_result.capped,
            needs_live_bfs=False,
        )

    verified = hint_search.verify_real_article(client, guess_tiles)
    if verified.unavailable:
        return _WrongGuessResolution(None, None, None, True, needs_live_bfs=False)
    if not verified.found:
        raise GameError("That's not a real English Wikipedia article title.", status_code=422)

    return _WrongGuessResolution(
        pageid=verified.pageid,
        title=verified.title,
        degrees_value=None,
        degrees_capped=False,
        needs_live_bfs=True,
    )


def _spawn_live_degrees_computation(
    article_id: int, attempt_id: int, guess_pageid: int, client: MediaWikiClient, degrees_config: dict
) -> None:
    """Runs the bounded live BFS in a background thread and writes the
    result back onto the already-committed GuessAttempt row once it's done,
    flipping degrees_pending off. A fresh app context (and therefore a fresh
    scoped session) is required since Flask-SQLAlchemy's session is tied to
    the request's context, which will be gone by the time this runs.
    """
    app = current_app._get_current_object()

    def worker() -> None:
        with app.app_context():
            try:
                article = db.session.get(Article, article_id)
                result = degrees_lib.compute_degrees_live(
                    client,
                    article,
                    guess_pageid,
                    depth_cap=degrees_config["depth_cap"],
                    node_cap=degrees_config["node_cap"],
                    timeout_sec=degrees_config["timeout_sec"],
                )
                degrees_value, degrees_capped = result.degrees, result.capped
            except Exception:
                logger.exception("Background live-degrees computation failed for attempt_id=%s", attempt_id)
                degrees_value, degrees_capped = None, True
                # A failure here (e.g. a lock-wait timeout from
                # opportunistic caching racing another writer) leaves this
                # session's transaction in a rolled-back state -- reusing it
                # without rolling back first raises PendingRollbackError,
                # which would silently kill this thread *before* the
                # attempt row below ever gets updated, stranding
                # degrees_pending=True forever. Confirmed live: exactly this
                # happened when a precompute run collided with a live guess
                # on the same article.
                db.session.rollback()

            try:
                attempt = db.session.get(GuessAttempt, attempt_id)
                if attempt is not None:
                    attempt.degrees_value = degrees_value
                    attempt.degrees_capped = degrees_capped
                    attempt.degrees_pending = False
                    db.session.commit()
            except Exception:
                logger.exception("Failed to persist degrees result for attempt_id=%s", attempt_id)
                db.session.rollback()

    threading.Thread(target=worker, daemon=True).start()


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

    guess_tiles = (guess_text or "").strip()
    if not guess_tiles:
        raise GameError("Guess text is required.")
    check_guess_shape(article, guess_tiles)

    if any(g.raw_guess_text.lower() == guess_tiles.lower() for g in session_row.guess_attempts):
        raise GameError("You already tried that guess.", status_code=409)

    answer_tiles = normalize_to_tiles(article.display_title)
    is_correct = guess_tiles.lower() == answer_tiles.lower()

    resolved = None if is_correct else _resolve_wrong_guess(article, guess_tiles, client)
    raw_score = score_lexical(guess_tiles, answer_tiles)
    bucket = bucket_lexical(raw_score)

    if is_correct:
        degrees_value, degrees_capped, degrees_pending = 0, False, False
        resolved_title, resolved_pageid = article.display_title, article.wiki_pageid
    elif resolved.needs_live_bfs:
        degrees_value, degrees_capped, degrees_pending = None, False, True
        resolved_title, resolved_pageid = resolved.title, resolved.pageid
    else:
        degrees_value, degrees_capped, degrees_pending = resolved.degrees_value, resolved.degrees_capped, False
        resolved_title, resolved_pageid = resolved.title, resolved.pageid

    attempt_number = session_row.guesses_made + 1
    attempt = GuessAttempt(
        game_session_id=session_row.id,
        attempt_number=attempt_number,
        raw_guess_text=guess_tiles,
        resolved_title=resolved_title,
        resolved_pageid=resolved_pageid,
        lexical_score_bucket=bucket,
        lexical_score_raw=raw_score,
        degrees_value=degrees_value,
        degrees_capped=degrees_capped,
        degrees_pending=degrees_pending,
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

    # Only today's puzzle counts toward stats -- replaying an archived day
    # (see get_challenge_for_date / list_archive) must not perturb streaks,
    # win distribution, or games_played.
    counts_toward_stats = daily_challenge.challenge_date == today_utc()
    if session_row.status in ("won", "lost") and session_row.user_id and counts_toward_stats:
        _update_user_stats(
            session_row.user_id,
            won=session_row.status == "won",
            attempt_number=session_row.solved_on_guess_number,
        )

    db.session.commit()

    if degrees_pending:
        _spawn_live_degrees_computation(article.id, attempt.id, resolved_pageid, client, degrees_config)

    return attempt
