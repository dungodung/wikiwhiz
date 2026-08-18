from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from backend.app.extensions import db
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge


@pytest.fixture()
def fixture_challenge(db):
    article = Article(
        wiki_title="Albert Einstein",
        wiki_pageid=736,
        display_title="Albert Einstein",
        slot_pattern=[{"type": "word", "len": 6}, {"type": "space"}, {"type": "word", "len": 8}],
        summary_extract="A theoretical physicist.",
        status="ready",
    )
    db.session.add(article)
    db.session.flush()

    clue_ids = []
    for i, (clue_type, text) in enumerate(
        [
            ("categories", "This person is associated with two obscure categories."),
            ("etymology", "Their surname has Germanic roots."),
            ("infobox_fact", "Born in the German Empire."),
            ("wikidata_fact", "Notable for a famous mass-energy equivalence formula."),
            ("commons_image", "A portrait photo is available."),
        ]
    ):
        clue = Clue(article_id=article.id, clue_type=clue_type, reveal_rank_hint=i + 1, clue_text=text)
        db.session.add(clue)
        db.session.flush()
        clue_ids.append(clue.id)

    challenge = DailyChallenge(
        challenge_date=date.today(),
        article_id=article.id,
        clue_order=clue_ids,
    )
    db.session.add(challenge)
    db.session.commit()
    return article, challenge


def test_today_creates_anon_session_and_reveals_first_clue(client, fixture_challenge):
    resp = client.get("/api/game/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert len(data["clues_revealed"]) == 1
    assert data["total_clues_available"] == 5
    assert "wikiwhiz_anon" in resp.headers.get("Set-Cookie", "")


def test_wrong_guess_reveals_next_clue(client, fixture_challenge):
    with patch("backend.app.blueprints.game.service.resolve_guess_text", return_value=None):
        resp = client.post("/api/game/guess", json={"guess_text": "Isaac Newton"})
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert len(data["clues_revealed"]) == 2
    assert data["guesses"][0]["is_correct"] is False


def test_correct_guess_wins(client, fixture_challenge):
    article, _ = fixture_challenge
    with patch(
        "backend.app.blueprints.game.service.resolve_guess_text",
        return_value={"pageid": article.wiki_pageid, "title": article.wiki_title},
    ), patch("backend.app.blueprints.game.service.degrees_lib.compute_degrees") as mock_degrees:
        mock_degrees.return_value.degrees = 0
        mock_degrees.return_value.capped = False
        resp = client.post("/api/game/guess", json={"guess_text": "Albert Einstein"})
    data = resp.get_json()
    assert data["status"] == "won"
    assert data["solved_answer_title"] == "Albert Einstein"


def test_running_out_of_clues_loses(client, fixture_challenge):
    with patch("backend.app.blueprints.game.service.resolve_guess_text", return_value=None):
        for _ in range(5):
            resp = client.post("/api/game/guess", json={"guess_text": "wrong"})
    data = resp.get_json()
    assert data["status"] == "lost"
    assert data["solved_answer_title"] == "Albert Einstein"


def test_refresh_does_not_reshuffle_clue_order(client, fixture_challenge):
    first = client.get("/api/game/today").get_json()
    second = client.get("/api/game/today").get_json()
    assert first["clues_revealed"] == second["clues_revealed"]
