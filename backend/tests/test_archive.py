from datetime import date, timedelta

import pytest

from backend.app.extensions import db
from backend.app.lib.slot_pattern import normalize_to_tiles, tile_shape
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge
from backend.app.models.stats import UserStats
from backend.app.models.user import User


def _make_article_and_challenge(db, title, pageid, on_date):
    article = Article(
        wiki_title=title,
        wiki_pageid=pageid,
        display_title=title,
        slot_pattern=tile_shape(title),
        status="ready",
    )
    db.session.add(article)
    db.session.flush()

    clue_ids = []
    for i in range(5):
        c = Clue(article_id=article.id, clue_type="categories", reveal_rank_hint=i + 1, clue_text=f"clue {i}")
        db.session.add(c)
        db.session.flush()
        clue_ids.append(c.id)

    challenge = DailyChallenge(challenge_date=on_date, article_id=article.id, clue_order=clue_ids)
    db.session.add(challenge)
    db.session.commit()
    return article, challenge


@pytest.fixture()
def logged_in_user(db, client):
    user = User(wikimedia_sub="sub-1", wikimedia_username="Alice")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
    return user


def test_archive_lists_past_days_not_future(client, db):
    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)
    _make_article_and_challenge(db, "Yesterday Article", 1, yesterday)
    _make_article_and_challenge(db, "Tomorrow Article", 2, tomorrow)

    resp = client.get("/api/game/archive")
    dates = [d["challenge_date"] for d in resp.get_json()["days"]]
    assert yesterday.isoformat() in dates
    assert tomorrow.isoformat() not in dates


def test_future_day_returns_404(client, db):
    tomorrow = date.today() + timedelta(days=1)
    _make_article_and_challenge(db, "Future Article", 3, tomorrow)
    resp = client.get(f"/api/game/day/{tomorrow.isoformat()}")
    assert resp.status_code == 404


def test_winning_archived_day_does_not_touch_stats(client, db, logged_in_user):
    yesterday = date.today() - timedelta(days=1)
    article, _ = _make_article_and_challenge(db, "Archived Win", 4, yesterday)

    resp = client.post(
        f"/api/game/day/{yesterday.isoformat()}/guess",
        json={"guess_text": normalize_to_tiles(article.display_title)},
    )

    assert resp.get_json()["status"] == "won"
    stats = db.session.get(UserStats, logged_in_user.id)
    assert stats is None  # never created -- archived play must not touch stats


def test_winning_todays_day_does_update_stats(client, db, logged_in_user):
    article, _ = _make_article_and_challenge(db, "Today Win", 5, date.today())

    resp = client.post(
        "/api/game/guess",
        json={"guess_text": normalize_to_tiles(article.display_title)},
    )

    assert resp.get_json()["status"] == "won"
    stats = db.session.get(UserStats, logged_in_user.id)
    assert stats is not None
    assert stats.games_won == 1
