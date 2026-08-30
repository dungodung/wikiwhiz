from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.app.extensions import db
from backend.app.lib.slot_pattern import tile_shape
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge
from backend.app.models.link_cache import LinkCacheMeta
from backend.app.models.session import GameSession
from backend.app.models.user import User


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


@pytest.fixture()
def admin_user(db, client):
    user = User(wikimedia_sub="admin-sub", wikimedia_username="AdminAlice", is_admin=True)
    db.session.add(user)
    db.session.commit()
    _login(client, user)
    return user


@pytest.fixture()
def plain_user(db, client):
    user = User(wikimedia_sub="plain-sub", wikimedia_username="PlainBob", is_admin=False)
    db.session.add(user)
    db.session.commit()
    return user


def _make_ready_article(db, title="Test Subject", pageid=100, n_clues=5):
    article = Article(
        wiki_title=title,
        wiki_pageid=pageid,
        display_title=title,
        slot_pattern=tile_shape(title),
        status="draft",
    )
    db.session.add(article)
    db.session.flush()
    for i in range(n_clues):
        db.session.add(Clue(article_id=article.id, clue_type="categories", reveal_rank_hint=i + 1, clue_text=f"fact {i}"))
    db.session.flush()
    article.status = "ready"
    db.session.commit()
    return article


# --- authz ---------------------------------------------------------------

def test_admin_route_requires_login(client, db):
    resp = client.get("/api/admin/users")
    assert resp.status_code == 401


def test_admin_route_requires_admin_flag(client, db, plain_user):
    _login(client, plain_user)
    resp = client.get("/api/admin/users")
    assert resp.status_code == 403


def test_admin_route_allows_admin(client, db, admin_user):
    resp = client.get("/api/admin/users")
    assert resp.status_code == 200


# --- user promotion --------------------------------------------------------

def test_promote_and_demote_user(client, db, admin_user, plain_user):
    resp = client.post(f"/api/admin/users/{plain_user.id}/promote")
    assert resp.status_code == 200
    assert resp.get_json()["is_admin"] is True

    resp = client.post(f"/api/admin/users/{plain_user.id}/demote")
    assert resp.status_code == 200
    assert resp.get_json()["is_admin"] is False


def test_cannot_demote_last_admin(client, db, admin_user):
    resp = client.post(f"/api/admin/users/{admin_user.id}/demote")
    assert resp.status_code == 409


# --- article/clue CRUD ------------------------------------------------------

def test_create_article_and_clue_then_reject_leaking_clue(client, db, admin_user):
    resp = client.post(
        "/api/admin/articles",
        json={"wiki_title": "Marie Curie", "wiki_pageid": 200, "display_title": "Marie Curie"},
    )
    assert resp.status_code == 201
    article_id = resp.get_json()["id"]

    resp = client.post(
        "/api/admin/clues",
        json={"article_id": article_id, "clue_type": "categories", "clue_text": "Marie Curie won two Nobel prizes."},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "clue_leaks_title"

    resp = client.post(
        "/api/admin/clues",
        json={"article_id": article_id, "clue_type": "categories", "clue_text": "Won two Nobel prizes in different sciences."},
    )
    assert resp.status_code == 201


def test_list_articles_sorts_ascending_by_created_at(client, db, admin_user):
    """Matches admin/schedule's own ordering (oldest/earliest first) --
    previously this was newest-first (created_at.desc()).
    """
    older = _make_ready_article(db, title="Older One", pageid=301)
    newer = _make_ready_article(db, title="Newer One", pageid=302)
    older.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    newer.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()

    resp = client.get("/api/admin/articles")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.get_json()["articles"]]
    assert ids.index(older.id) < ids.index(newer.id)


def test_list_articles_includes_link_cache_count(client, db, admin_user):
    with_cache = _make_ready_article(db, title="Has Cache", pageid=303)
    without_cache = _make_ready_article(db, title="No Cache Yet", pageid=304)
    db.session.add(LinkCacheMeta(answer_article_id=with_cache.id, node_count=42, status="complete"))
    db.session.commit()

    resp = client.get("/api/admin/articles")
    articles_by_id = {a["id"]: a for a in resp.get_json()["articles"]}
    assert articles_by_id[with_cache.id]["link_cache_count"] == 42
    assert articles_by_id[without_cache.id]["link_cache_count"] is None


def test_cannot_edit_or_delete_locked_article(client, db, admin_user):
    article = _make_ready_article(db, title="Locked One", pageid=201)
    challenge = DailyChallenge(challenge_date=date.today(), article_id=article.id, clue_order=[c.id for c in article.clues])
    db.session.add(challenge)
    db.session.commit()

    resp = client.patch(f"/api/admin/articles/{article.id}", json={"summary_extract": "nope"})
    assert resp.status_code == 409

    resp = client.delete(f"/api/admin/articles/{article.id}")
    assert resp.status_code == 409


def test_can_edit_future_scheduled_article_clues(client, db, admin_user):
    article = _make_ready_article(db, title="Future One", pageid=202)
    challenge = DailyChallenge(
        challenge_date=date.today() + timedelta(days=5),
        article_id=article.id,
        clue_order=[c.id for c in article.clues],
    )
    db.session.add(challenge)
    db.session.commit()
    clue_id = article.clues[0].id

    resp = client.patch(f"/api/admin/clues/{clue_id}", json={"clue_text": "A better-worded fact."})
    assert resp.status_code == 200
    assert resp.get_json()["clue_text"] == "A better-worded fact."


# --- scheduling --------------------------------------------------------

def test_schedule_and_reassign_swap(client, db, admin_user):
    article_a = _make_ready_article(db, title="Article A", pageid=300)
    article_b = _make_ready_article(db, title="Article B", pageid=301)
    target_date = (date.today() + timedelta(days=10)).isoformat()

    resp = client.post(f"/api/admin/articles/{article_a.id}/schedule", json={"date": target_date})
    assert resp.status_code == 200
    assert resp.get_json()["challenge_date"] == target_date

    # Reassigning the same date to article_b should free article_a back to 'ready'
    resp = client.post(f"/api/admin/schedule/{target_date}/assign", json={"article_id": article_b.id})
    assert resp.status_code == 200

    db.session.refresh(article_a)
    db.session.refresh(article_b)
    assert article_a.status == "ready"
    assert article_a.daily_challenge is None
    assert article_b.status == "scheduled"
    assert article_b.daily_challenge.challenge_date.isoformat() == target_date


def test_cannot_modify_schedule_for_past_or_today(client, db, admin_user):
    article = _make_ready_article(db, title="Article C", pageid=302)
    today = date.today().isoformat()

    resp = client.post(f"/api/admin/schedule/{today}/assign", json={"article_id": article.id})
    assert resp.status_code == 400

    resp = client.delete(f"/api/admin/schedule/{today}")
    assert resp.status_code == 400


def test_unschedule_future_date(client, db, admin_user):
    article = _make_ready_article(db, title="Article D", pageid=303)
    target_date = (date.today() + timedelta(days=3)).isoformat()
    client.post(f"/api/admin/articles/{article.id}/schedule", json={"date": target_date})

    resp = client.delete(f"/api/admin/schedule/{target_date}")
    assert resp.status_code == 204

    db.session.refresh(article)
    assert article.status == "ready"
    assert article.daily_challenge is None


# --- article lookup (add-article popup autocomplete/auto-fill) -----------

def test_article_lookup_search_requires_admin(client, db, plain_user):
    _login(client, plain_user)
    resp = client.get("/api/admin/article-lookup/search?q=Alb")
    assert resp.status_code == 403


def test_article_lookup_search_blank_query_returns_no_results(client, db, admin_user):
    resp = client.get("/api/admin/article-lookup/search?q=")
    assert resp.status_code == 200
    assert resp.get_json() == {"results": []}


def test_article_lookup_search_returns_prefix_matches(client, db, admin_user):
    fake_results = [{"title": "Albert Einstein", "pageid": 736}, {"title": "Albert Camus", "pageid": 1234}]
    with patch("backend.app.lib.mediawiki_api.MediaWikiClient.prefix_search", return_value=fake_results) as mock_search:
        resp = client.get("/api/admin/article-lookup/search?q=Alb")

    assert resp.status_code == 200
    assert resp.get_json() == {"results": fake_results}
    mock_search.assert_called_once_with("Alb", limit=8)


def test_article_lookup_resolve_requires_title(client, db, admin_user):
    resp = client.get("/api/admin/article-lookup/resolve")
    assert resp.status_code == 400


def test_article_lookup_resolve_not_found(client, db, admin_user):
    with patch("backend.app.lib.mediawiki_api.MediaWikiClient.resolve_title", return_value=None):
        resp = client.get("/api/admin/article-lookup/resolve?title=Not+A+Real+Page")
    assert resp.status_code == 404


def test_article_lookup_resolve_fills_summary_from_wikidata(client, db, admin_user):
    with (
        patch(
            "backend.app.lib.mediawiki_api.MediaWikiClient.resolve_title",
            return_value={"pageid": 736, "title": "Albert Einstein"},
        ),
        patch("backend.app.lib.mediawiki_api.MediaWikiClient.get_wikibase_item", return_value="Q937"),
        patch(
            "backend.app.lib.mediawiki_api.MediaWikiClient.fetch_wikidata_description",
            return_value="German-born theoretical physicist",
        ),
    ):
        resp = client.get("/api/admin/article-lookup/resolve?title=albert einstein")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "wiki_title": "Albert Einstein",
        "wiki_pageid": 736,
        "display_title": "Albert Einstein",
        "summary_extract": "German-born theoretical physicist",
    }


def test_article_lookup_resolve_no_wikidata_item_leaves_summary_null(client, db, admin_user):
    with (
        patch(
            "backend.app.lib.mediawiki_api.MediaWikiClient.resolve_title",
            return_value={"pageid": 42, "title": "Some Obscure Page"},
        ),
        patch("backend.app.lib.mediawiki_api.MediaWikiClient.get_wikibase_item", return_value=None),
    ):
        resp = client.get("/api/admin/article-lookup/resolve?title=Some Obscure Page")

    assert resp.status_code == 200
    assert resp.get_json()["summary_extract"] is None


# --- article stats ---------------------------------------------------------

def test_article_stats_requires_admin(client, db, plain_user):
    _login(client, plain_user)
    resp = client.get("/api/admin/article-stats")
    assert resp.status_code == 403


def test_article_stats_aggregates_sessions_correctly(client, db, admin_user, plain_user):
    article = _make_ready_article(db, title="Stats Subject", pageid=400)
    past_date = date.today() - timedelta(days=2)
    challenge = DailyChallenge(
        challenge_date=past_date, article_id=article.id, clue_order=[c.id for c in article.clues]
    )
    db.session.add(challenge)
    db.session.flush()

    # A future, never-played challenge -- must not show up in results at all.
    future_article = _make_ready_article(db, title="Future Subject", pageid=401)
    db.session.add(
        DailyChallenge(
            challenge_date=date.today() + timedelta(days=5),
            article_id=future_article.id,
            clue_order=[c.id for c in future_article.clues],
        )
    )

    second_registered = User(wikimedia_sub="second-sub", wikimedia_username="SecondUser", is_admin=False)
    db.session.add(second_registered)
    db.session.flush()

    sessions = [
        GameSession(daily_challenge_id=challenge.id, user_id=plain_user.id, status="won", solved_on_guess_number=2),
        GameSession(daily_challenge_id=challenge.id, user_id=second_registered.id, status="won", solved_on_guess_number=4),
        GameSession(daily_challenge_id=challenge.id, anon_token="anon-1", status="won", solved_on_guess_number=6),
        GameSession(daily_challenge_id=challenge.id, anon_token="anon-2", status="lost"),
        GameSession(daily_challenge_id=challenge.id, user_id=None, anon_token="anon-3", status="in_progress"),
    ]
    db.session.add_all(sessions)
    db.session.commit()

    resp = client.get("/api/admin/article-stats")
    assert resp.status_code == 200
    rows = {r["article_id"]: r for r in resp.get_json()["articles"]}

    assert future_article.id not in rows
    row = rows[article.id]
    assert row["display_title"] == "Stats Subject"
    assert row["challenge_date"] == past_date.isoformat()
    assert row["attempted"] == 5
    assert row["won_total"] == 3
    assert row["won_registered"] == 2
    assert row["failed_total"] == 1
    assert row["failed_registered"] == 0
    assert row["avg_win_guess"] == 4.0  # (2 + 4 + 6) / 3


# --- pagination --------------------------------------------------------

def test_list_users_paginates_default_20_per_page(client, db, admin_user):
    for i in range(24):  # + admin_user itself = 25 total
        db.session.add(User(wikimedia_sub=f"sub-{i}", wikimedia_username=f"User{i:02d}", is_admin=False))
    db.session.commit()

    resp = client.get("/api/admin/users")
    data = resp.get_json()
    assert len(data["users"]) == 20
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert data["total"] == 25
    assert data["total_pages"] == 2

    resp = client.get("/api/admin/users?page=2")
    data = resp.get_json()
    assert len(data["users"]) == 5
    assert data["page"] == 2


def test_list_articles_paginates_and_respects_per_page_override(client, db, admin_user):
    for i in range(25):
        _make_ready_article(db, title=f"Paged Article {i}", pageid=500 + i)

    resp = client.get("/api/admin/articles")
    data = resp.get_json()
    assert len(data["articles"]) == 20
    assert data["total"] == 25
    assert data["total_pages"] == 2

    resp = client.get("/api/admin/articles?per_page=10&page=3")
    data = resp.get_json()
    assert len(data["articles"]) == 5  # 25 total: page 3 of size 10 -> last 5
    assert data["page"] == 3
    assert data["per_page"] == 10


def test_list_schedule_paginates(client, db, admin_user):
    for i in range(25):
        article = _make_ready_article(db, title=f"Scheduled {i}", pageid=600 + i)
        db.session.add(
            DailyChallenge(
                challenge_date=date.today() + timedelta(days=i + 1),
                article_id=article.id,
                clue_order=[c.id for c in article.clues],
            )
        )
    db.session.commit()

    resp = client.get("/api/admin/schedule")
    data = resp.get_json()
    assert len(data["days"]) == 20
    assert data["total"] == 25
    # Ascending by date -- the first page holds the nearest (soonest) days.
    assert data["days"][0]["challenge_date"] == (date.today() + timedelta(days=1)).isoformat()

    resp = client.get("/api/admin/schedule?page=2")
    data = resp.get_json()
    assert len(data["days"]) == 5


def test_article_stats_paginates(client, db, admin_user):
    for i in range(25):
        article = _make_ready_article(db, title=f"Stats {i}", pageid=700 + i)
        db.session.add(
            DailyChallenge(
                challenge_date=date.today() - timedelta(days=i + 1),
                article_id=article.id,
                clue_order=[c.id for c in article.clues],
            )
        )
    db.session.commit()

    resp = client.get("/api/admin/article-stats")
    data = resp.get_json()
    assert len(data["articles"]) == 20
    assert data["total"] == 25
    assert data["total_pages"] == 2


# --- "past" status filter -----------------------------------------------

def _make_scheduled_article(db, *, title, pageid, challenge_date):
    article = _make_ready_article(db, title=title, pageid=pageid)
    db.session.add(
        DailyChallenge(challenge_date=challenge_date, article_id=article.id, clue_order=[c.id for c in article.clues])
    )
    article.status = "scheduled"
    db.session.commit()
    return article


def test_scheduled_filter_excludes_past_days(client, db, admin_user):
    past = _make_scheduled_article(db, title="Past Day", pageid=800, challenge_date=date.today() - timedelta(days=1))
    future = _make_scheduled_article(db, title="Future Day", pageid=801, challenge_date=date.today() + timedelta(days=1))

    resp = client.get("/api/admin/articles?status=scheduled")
    ids = {a["id"] for a in resp.get_json()["articles"]}
    assert future.id in ids
    assert past.id not in ids


def test_past_filter_shows_only_played_out_days(client, db, admin_user):
    past = _make_scheduled_article(db, title="Past Day 2", pageid=802, challenge_date=date.today() - timedelta(days=1))
    future = _make_scheduled_article(db, title="Future Day 2", pageid=803, challenge_date=date.today() + timedelta(days=1))

    resp = client.get("/api/admin/articles?status=past")
    data = resp.get_json()["articles"]
    ids = {a["id"] for a in data}
    assert past.id in ids
    assert future.id not in ids
    assert next(a for a in data if a["id"] == past.id)["display_status"] == "past"
    # The underlying stored status is untouched -- still genuinely 'scheduled'.
    assert next(a for a in data if a["id"] == past.id)["status"] == "scheduled"


def test_all_filter_includes_past_days(client, db, admin_user):
    past = _make_scheduled_article(db, title="Past Day 3", pageid=804, challenge_date=date.today() - timedelta(days=1))

    resp = client.get("/api/admin/articles")  # no status param == "All"
    ids = {a["id"] for a in resp.get_json()["articles"]}
    assert past.id in ids


def test_future_scheduled_article_display_status_stays_scheduled(client, db, admin_user):
    future = _make_scheduled_article(db, title="Future Day 3", pageid=805, challenge_date=date.today() + timedelta(days=1))

    resp = client.get("/api/admin/articles?status=scheduled")
    row = next(a for a in resp.get_json()["articles"] if a["id"] == future.id)
    assert row["display_status"] == "scheduled"


# --- sorting --------------------------------------------------------------

def test_list_articles_sorts_by_title_descending(client, db, admin_user):
    _make_ready_article(db, title="Aardvark", pageid=810)
    _make_ready_article(db, title="Zebra", pageid=811)

    resp = client.get("/api/admin/articles?sort=title&order=desc")
    titles = [a["display_title"] for a in resp.get_json()["articles"]]
    assert titles.index("Zebra") < titles.index("Aardvark")


def test_list_articles_sorts_by_clue_count(client, db, admin_user):
    _make_ready_article(db, title="Few Clues", pageid=812, n_clues=5)
    _make_ready_article(db, title="Many Clues", pageid=813, n_clues=7)

    resp = client.get("/api/admin/articles?sort=clue_count&order=desc")
    titles = [a["display_title"] for a in resp.get_json()["articles"]]
    assert titles.index("Many Clues") < titles.index("Few Clues")


def test_list_articles_rejects_unknown_sort_key(client, db, admin_user):
    _make_ready_article(db, title="Whatever", pageid=814)
    resp = client.get("/api/admin/articles?sort=not_a_real_column")
    assert resp.status_code == 200  # falls back to the default sort rather than erroring


def test_list_users_defaults_to_newest_joined_first(client, db, admin_user):
    older = User(wikimedia_sub="older-sub", wikimedia_username="OlderUser", is_admin=False)
    newer = User(wikimedia_sub="newer-sub", wikimedia_username="NewerUser", is_admin=False)
    db.session.add_all([older, newer])
    db.session.flush()
    older.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    newer.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()

    resp = client.get("/api/admin/users")  # no sort param -- default
    usernames = [u["username"] for u in resp.get_json()["users"]]
    assert usernames.index("NewerUser") < usernames.index("OlderUser")


def test_list_users_sorts_by_username_descending(client, db, admin_user):
    db.session.add(User(wikimedia_sub="z-sub", wikimedia_username="ZUser", is_admin=False))
    db.session.commit()

    resp = client.get("/api/admin/users?sort=username&order=desc")
    usernames = [u["username"] for u in resp.get_json()["users"]]
    assert usernames[0] == "ZUser"


def test_list_schedule_sorts_by_article_title(client, db, admin_user):
    _make_scheduled_article(db, title="Aardvark Day", pageid=820, challenge_date=date.today() + timedelta(days=1))
    _make_scheduled_article(db, title="Zebra Day", pageid=821, challenge_date=date.today() + timedelta(days=2))

    resp = client.get("/api/admin/schedule?sort=article&order=desc")
    titles = [d["display_title"] for d in resp.get_json()["days"]]
    assert titles.index("Zebra Day") < titles.index("Aardvark Day")


def test_article_stats_default_sort_stays_newest_first(client, db, admin_user):
    older = _make_scheduled_article(db, title="Older Stat", pageid=830, challenge_date=date.today() - timedelta(days=5))
    newer = _make_scheduled_article(db, title="Newer Stat", pageid=831, challenge_date=date.today() - timedelta(days=1))

    resp = client.get("/api/admin/article-stats")
    ids = [a["article_id"] for a in resp.get_json()["articles"]]
    assert ids.index(newer.id) < ids.index(older.id)


def test_article_stats_sorts_by_attempted_ascending(client, db, admin_user, plain_user):
    quiet = _make_scheduled_article(db, title="Quiet Day", pageid=832, challenge_date=date.today() - timedelta(days=3))
    busy = _make_scheduled_article(db, title="Busy Day", pageid=833, challenge_date=date.today() - timedelta(days=2))
    quiet_challenge = quiet.daily_challenge
    busy_challenge = busy.daily_challenge
    db.session.add(GameSession(daily_challenge_id=quiet_challenge.id, user_id=plain_user.id, status="lost"))
    db.session.add_all(
        [
            GameSession(daily_challenge_id=busy_challenge.id, anon_token="a1", status="lost"),
            GameSession(daily_challenge_id=busy_challenge.id, anon_token="a2", status="lost"),
            GameSession(daily_challenge_id=busy_challenge.id, anon_token="a3", status="lost"),
        ]
    )
    db.session.commit()

    resp = client.get("/api/admin/article-stats?sort=attempted&order=asc")
    ids = [a["article_id"] for a in resp.get_json()["articles"]]
    assert ids.index(quiet.id) < ids.index(busy.id)
