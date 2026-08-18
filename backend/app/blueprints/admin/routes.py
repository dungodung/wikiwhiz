"""Admin API: user promotion, and management of *future, unplayed* articles
and clues. Today's and past daily_challenges are immutable here on purpose --
editing something a player has already seen (or is currently playing) would
be confusing at best and stat-corrupting at worst. Every mutation reuses the
same lib functions the CLI content-authoring scripts use
(lib/clue_guard.py, lib/scheduling.py) so admin edits and skill-authored
content are held to identical rules.
"""

from datetime import date as date_cls
from datetime import timedelta

from flask import Blueprint, jsonify, request

from ...extensions import db
from ...lib.authz import require_admin
from ...lib.clue_guard import can_promote_to_ready, leaks_title, usable_clue_count
from ...lib.scheduling import SchedulingError, schedule_article, unschedule_article
from ...lib.slot_pattern import tokenize_title_to_slots
from ...blueprints.game.service import today_utc
from ...models.article import Article
from ...models.clue import CLUE_TYPES, Clue
from ...models.daily_challenge import DailyChallenge
from ...models.user import User

admin_bp = Blueprint("admin", __name__)


def _parse_date(date_str: str) -> date_cls | None:
    try:
        return date_cls.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _article_is_locked(article: Article) -> bool:
    """Locked once its scheduled date is today or in the past."""
    dc = article.daily_challenge
    return dc is not None and dc.challenge_date <= today_utc()


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.wikimedia_username,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _serialize_clue(clue: Clue) -> dict:
    return {
        "id": clue.id,
        "article_id": clue.article_id,
        "clue_type": clue.clue_type,
        "reveal_rank_hint": clue.reveal_rank_hint,
        "clue_text": clue.clue_text,
        "clue_media_url": clue.clue_media_url,
        "is_title_leaking": clue.is_title_leaking,
    }


def _serialize_article(article: Article, include_clues: bool = False) -> dict:
    dc = article.daily_challenge
    data = {
        "id": article.id,
        "wiki_title": article.wiki_title,
        "wiki_pageid": article.wiki_pageid,
        "display_title": article.display_title,
        "summary_extract": article.summary_extract,
        "source_notes": article.source_notes,
        "status": article.status,
        "difficulty_tier": article.difficulty_tier,
        "scheduled_date": dc.challenge_date.isoformat() if dc else None,
        "locked": _article_is_locked(article),
        "clue_count": usable_clue_count(db.session, article.id),
    }
    if include_clues:
        clues_by_id = {c.id: c for c in article.clues}
        if dc and dc.clue_order:
            ordered = [clues_by_id[cid] for cid in dc.clue_order if cid in clues_by_id]
        else:
            ordered = sorted(article.clues, key=lambda c: c.reveal_rank_hint)
        data["clues"] = [_serialize_clue(c) for c in ordered]
    return data


# --- Users -------------------------------------------------------------

@admin_bp.get("/users")
@require_admin
def list_users():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter(User.wikimedia_username.ilike(f"%{q}%"))
    users = query.order_by(User.wikimedia_username).limit(50).all()
    return jsonify({"users": [_serialize_user(u) for u in users]})


@admin_bp.post("/users/<int:user_id>/promote")
@require_admin
def promote_user(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "not_found"}), 404
    user.is_admin = True
    db.session.commit()
    return jsonify(_serialize_user(user))


@admin_bp.post("/users/<int:user_id>/demote")
@require_admin
def demote_user(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "not_found"}), 404
    if user.is_admin:
        other_admins = User.query.filter(User.is_admin.is_(True), User.id != user.id).count()
        if other_admins == 0:
            return jsonify({"error": "cannot_demote_last_admin"}), 409
    user.is_admin = False
    db.session.commit()
    return jsonify(_serialize_user(user))


# --- Articles ------------------------------------------------------------

@admin_bp.get("/articles")
@require_admin
def list_articles():
    status = request.args.get("status")
    query = Article.query
    if status:
        query = query.filter_by(status=status)
    articles = query.order_by(Article.created_at.desc()).limit(200).all()
    return jsonify({"articles": [_serialize_article(a) for a in articles]})


@admin_bp.get("/articles/<int:article_id>")
@require_admin
def get_article(article_id: int):
    article = db.session.get(Article, article_id)
    if not article:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_serialize_article(article, include_clues=True))


@admin_bp.post("/articles")
@require_admin
def create_article():
    payload = request.get_json(silent=True) or {}
    title, pageid, display_title = payload.get("wiki_title"), payload.get("wiki_pageid"), payload.get("display_title")
    if not (title and pageid and display_title):
        return jsonify({"error": "wiki_title, wiki_pageid, display_title are required"}), 400

    if Article.query.filter_by(wiki_pageid=pageid).first():
        return jsonify({"error": "duplicate_pageid"}), 409

    article = Article(
        wiki_title=title,
        wiki_pageid=pageid,
        display_title=display_title,
        slot_pattern=tokenize_title_to_slots(display_title),
        summary_extract=payload.get("summary_extract"),
        source_notes=payload.get("source_notes"),
        status="draft",
    )
    db.session.add(article)
    db.session.commit()
    return jsonify(_serialize_article(article)), 201


@admin_bp.patch("/articles/<int:article_id>")
@require_admin
def update_article(article_id: int):
    article = db.session.get(Article, article_id)
    if not article:
        return jsonify({"error": "not_found"}), 404
    if _article_is_locked(article):
        return jsonify({"error": "article_locked", "detail": "already live today or in the past"}), 409

    payload = request.get_json(silent=True) or {}
    if "summary_extract" in payload:
        article.summary_extract = payload["summary_extract"]
    if "source_notes" in payload:
        article.source_notes = payload["source_notes"]
    if "difficulty_tier" in payload:
        article.difficulty_tier = payload["difficulty_tier"]
    if "status" in payload:
        new_status = payload["status"]
        if new_status == "ready":
            ok, count = can_promote_to_ready(db.session, article)
            if not ok:
                return jsonify({"error": "not_enough_clues", "clue_count": count}), 400
        article.status = new_status

    db.session.commit()
    return jsonify(_serialize_article(article))


@admin_bp.delete("/articles/<int:article_id>")
@require_admin
def delete_article(article_id: int):
    article = db.session.get(Article, article_id)
    if not article:
        return jsonify({"error": "not_found"}), 404
    if _article_is_locked(article):
        return jsonify({"error": "article_locked", "detail": "already live today or in the past"}), 409

    db.session.delete(article)  # cascades to clues; daily_challenge FK has no cascade, but locked check above guarantees none exists in the past/today -- a future one is fine to cascade-delete too
    db.session.commit()
    return "", 204


# --- Clues -----------------------------------------------------------------

@admin_bp.post("/clues")
@require_admin
def create_clue():
    payload = request.get_json(silent=True) or {}
    article_id = payload.get("article_id")
    clue_type = payload.get("clue_type")
    clue_text = payload.get("clue_text", "").strip()

    article = db.session.get(Article, article_id) if article_id else None
    if not article:
        return jsonify({"error": "article_not_found"}), 404
    if _article_is_locked(article):
        return jsonify({"error": "article_locked"}), 409
    if clue_type not in CLUE_TYPES:
        return jsonify({"error": "invalid_clue_type"}), 400
    if not clue_text:
        return jsonify({"error": "clue_text_required"}), 400
    if leaks_title(clue_text, article):
        return jsonify({"error": "clue_leaks_title"}), 400

    clue = Clue(
        article_id=article.id,
        clue_type=clue_type,
        clue_text=clue_text,
        reveal_rank_hint=payload.get("reveal_rank_hint", 3),
        clue_media_url=payload.get("clue_media_url"),
        clue_payload=payload.get("clue_payload"),
        is_title_leaking=False,
    )
    db.session.add(clue)
    db.session.commit()
    return jsonify(_serialize_clue(clue)), 201


@admin_bp.patch("/clues/<int:clue_id>")
@require_admin
def update_clue(clue_id: int):
    clue = db.session.get(Clue, clue_id)
    if not clue:
        return jsonify({"error": "not_found"}), 404
    article = db.session.get(Article, clue.article_id)
    if _article_is_locked(article):
        return jsonify({"error": "article_locked"}), 409

    payload = request.get_json(silent=True) or {}
    if "clue_text" in payload:
        new_text = payload["clue_text"].strip()
        if not new_text:
            return jsonify({"error": "clue_text_required"}), 400
        if leaks_title(new_text, article):
            return jsonify({"error": "clue_leaks_title"}), 400
        clue.clue_text = new_text
    if "clue_type" in payload:
        if payload["clue_type"] not in CLUE_TYPES:
            return jsonify({"error": "invalid_clue_type"}), 400
        clue.clue_type = payload["clue_type"]
    if "reveal_rank_hint" in payload:
        clue.reveal_rank_hint = payload["reveal_rank_hint"]
    if "clue_media_url" in payload:
        clue.clue_media_url = payload["clue_media_url"]

    db.session.commit()
    return jsonify(_serialize_clue(clue))


@admin_bp.delete("/clues/<int:clue_id>")
@require_admin
def delete_clue(clue_id: int):
    clue = db.session.get(Clue, clue_id)
    if not clue:
        return jsonify({"error": "not_found"}), 404
    article = db.session.get(Article, clue.article_id)
    if _article_is_locked(article):
        return jsonify({"error": "article_locked"}), 409

    db.session.delete(clue)
    db.session.commit()
    return "", 204


@admin_bp.post("/articles/<int:article_id>/reorder-clues")
@require_admin
def reorder_clues(article_id: int):
    article = db.session.get(Article, article_id)
    if not article:
        return jsonify({"error": "not_found"}), 404
    if _article_is_locked(article):
        return jsonify({"error": "article_locked"}), 409

    payload = request.get_json(silent=True) or {}
    clue_ids = payload.get("clue_ids")
    if not isinstance(clue_ids, list) or not clue_ids:
        return jsonify({"error": "clue_ids_required"}), 400

    valid_ids = {c.id for c in article.clues}
    if not set(clue_ids).issubset(valid_ids):
        return jsonify({"error": "clue_ids_do_not_match_article"}), 400
    if not (5 <= len(clue_ids) <= 7):
        return jsonify({"error": "must_order_between_5_and_7_clues"}), 400

    if article.daily_challenge:
        article.daily_challenge.clue_order = clue_ids
    else:
        for rank, clue_id in enumerate(clue_ids, start=1):
            clue = next(c for c in article.clues if c.id == clue_id)
            clue.reveal_rank_hint = rank

    db.session.commit()
    return jsonify(_serialize_article(article, include_clues=True))


# --- Scheduling --------------------------------------------------------

@admin_bp.get("/schedule")
@require_admin
def list_schedule():
    from_date = _parse_date(request.args.get("from", "")) or today_utc()
    to_date = _parse_date(request.args.get("to", ""))
    if to_date is None:
        to_date = from_date + timedelta(days=30)

    challenges = (
        DailyChallenge.query.filter(
            DailyChallenge.challenge_date >= from_date, DailyChallenge.challenge_date <= to_date
        )
        .order_by(DailyChallenge.challenge_date)
        .all()
    )
    return jsonify(
        {
            "days": [
                {
                    "challenge_date": c.challenge_date.isoformat(),
                    "article_id": c.article_id,
                    "wiki_title": c.article.wiki_title,
                    "display_title": c.article.display_title,
                    "locked": c.challenge_date <= today_utc(),
                }
                for c in challenges
            ]
        }
    )


@admin_bp.post("/articles/<int:article_id>/schedule")
@require_admin
def schedule_article_route(article_id: int):
    article = db.session.get(Article, article_id)
    if not article:
        return jsonify({"error": "not_found"}), 404
    if article.status != "ready":
        return jsonify({"error": "article_not_ready"}), 400

    payload = request.get_json(silent=True) or {}
    on_date = _parse_date(payload.get("date")) if payload.get("date") else None
    if payload.get("date") and on_date is None:
        return jsonify({"error": "invalid_date"}), 400
    if on_date is not None and on_date <= today_utc():
        return jsonify({"error": "date_must_be_future"}), 400

    try:
        challenge = schedule_article(db.session, article, on_date=on_date)
        db.session.commit()
    except SchedulingError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify({"article_id": article.id, "challenge_date": challenge.challenge_date.isoformat()})


@admin_bp.post("/schedule/<date_str>/assign")
@require_admin
def assign_schedule_date(date_str: str):
    target_date = _parse_date(date_str)
    if target_date is None:
        return jsonify({"error": "invalid_date"}), 400
    if target_date <= today_utc():
        return jsonify({"error": "date_must_be_future"}), 400

    payload = request.get_json(silent=True) or {}
    article_id = payload.get("article_id")
    article = db.session.get(Article, article_id) if article_id else None
    if not article:
        return jsonify({"error": "article_not_found"}), 404
    if article.status not in ("ready", "scheduled"):
        return jsonify({"error": "article_not_ready"}), 400

    # Free up the target date if something else is scheduled there.
    existing = DailyChallenge.query.filter_by(challenge_date=target_date).first()
    if existing and existing.article_id != article.id:
        unschedule_article(db.session, existing)

    # If this article is already scheduled elsewhere in the future, move it.
    if article.daily_challenge and article.daily_challenge.challenge_date != target_date:
        if article.daily_challenge.challenge_date <= today_utc():
            return jsonify({"error": "article_already_locked_elsewhere"}), 409
        unschedule_article(db.session, article.daily_challenge)

    try:
        challenge = schedule_article(db.session, article, on_date=target_date)
        db.session.commit()
    except SchedulingError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify({"article_id": article.id, "challenge_date": challenge.challenge_date.isoformat()})


@admin_bp.delete("/schedule/<date_str>")
@require_admin
def unschedule_date(date_str: str):
    target_date = _parse_date(date_str)
    if target_date is None:
        return jsonify({"error": "invalid_date"}), 400
    if target_date <= today_utc():
        return jsonify({"error": "date_must_be_future"}), 400

    challenge = DailyChallenge.query.filter_by(challenge_date=target_date).first()
    if not challenge:
        return jsonify({"error": "not_found"}), 404

    unschedule_article(db.session, challenge)
    db.session.commit()
    return "", 204
