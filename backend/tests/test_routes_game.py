import threading
import time
from datetime import date
from unittest.mock import patch

import pytest

from backend.app.extensions import db
from backend.app.lib.degrees import DegreesResult
from backend.app.lib.hint_search import VerifyResult
from backend.app.lib.slot_pattern import tile_shape
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge
from backend.app.models.link_cache import LinkCacheNode

# A real (fictional-for-the-test) same-shape neighbor, cached ahead of time --
# this is what a genuine "wrong but real" guess resolves against, with no
# network call needed. Shape must match "Albert Einstein": 6 letters, space,
# 8 letters.
WRONG_GUESS = "Newton Physicsx"


@pytest.fixture()
def fixture_challenge(db):
    article = Article(
        wiki_title="Albert Einstein",
        wiki_pageid=736,
        display_title="Albert Einstein",
        slot_pattern=tile_shape("Albert Einstein"),
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

    db.session.add(
        LinkCacheNode(
            answer_article_id=article.id,
            node_pageid=999,
            node_title="Newton Physicsx",
            node_tiles=WRONG_GUESS.lower(),
            degree=2,
        )
    )
    db.session.commit()
    return article, challenge


def test_today_shows_fresh_state_without_creating_a_session(client, db, fixture_challenge):
    """Viewing a puzzle must be read-only -- a GameSession row (and the DB
    garbage that comes with idle visitors who never actually play) is only
    ever created on the first submitted guess. See service.get_session vs.
    get_or_create_session.
    """
    resp = client.get("/api/game/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert len(data["clues_revealed"]) == 1
    assert data["total_clues_available"] == 5
    assert data["slot_pattern"] == "L" * 15
    assert data["guesses"] == []
    assert "wikiwhiz_anon" in resp.headers.get("Set-Cookie", "")

    from backend.app.models.session import GameSession

    assert db.session.query(GameSession).count() == 0


def test_first_guess_creates_the_session(client, db, fixture_challenge):
    from backend.app.models.session import GameSession

    assert db.session.query(GameSession).count() == 0
    resp = client.post("/api/game/guess", json={"guess_text": WRONG_GUESS})
    assert resp.status_code == 200
    assert db.session.query(GameSession).count() == 1


def test_wrong_but_real_guess_reveals_next_clue(client, fixture_challenge):
    resp = client.post("/api/game/guess", json={"guess_text": WRONG_GUESS})
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert len(data["clues_revealed"]) == 2
    assert data["guesses"][0]["is_correct"] is False
    assert data["guesses"][0]["degrees_value"] == 2


def test_guess_with_wrong_length_is_rejected(client, fixture_challenge):
    resp = client.post("/api/game/guess", json={"guess_text": "TooShort"})
    assert resp.status_code == 400


def test_repeating_a_previous_guess_is_rejected_and_not_counted(client, fixture_challenge):
    first = client.post("/api/game/guess", json={"guess_text": WRONG_GUESS})
    assert first.status_code == 200
    assert len(first.get_json()["clues_revealed"]) == 2

    repeat = client.post("/api/game/guess", json={"guess_text": WRONG_GUESS.lower()})
    assert repeat.status_code == 409

    state = client.get("/api/game/today").get_json()
    assert len(state["guesses"]) == 1
    assert len(state["clues_revealed"]) == 2


def test_space_position_is_not_a_shape_constraint(client, fixture_challenge):
    """Nothing about the answer's shape is pre-revealed, including where the
    space falls -- a guess with a space in a different place than the real
    answer's (index 5 here, vs. the answer's index 6) is just a wrong guess,
    not a 400 shape violation.
    """
    with (
        patch(
            "backend.app.blueprints.game.service.hint_search.verify_real_article",
            return_value=VerifyResult(pageid=1, title="Some Other Fifteench"),
        ),
        patch(
            "backend.app.blueprints.game.service.degrees_lib.compute_degrees_live",
            return_value=DegreesResult(degrees=None, capped=True),
        ),
    ):
        resp = client.post("/api/game/guess", json={"guess_text": "Newto nPhysicsx"})
    assert resp.status_code == 200
    assert resp.get_json()["guesses"][0]["is_correct"] is False


def test_slow_degrees_computation_does_not_block_the_guess_response(client, fixture_challenge):
    """A guess confirmed real but not cache-hit must be accepted immediately
    (degrees_pending=True, degrees_value=None) without waiting on the live
    BFS -- which can take anywhere from a couple of seconds to 20+ for two
    hub-like articles. The BFS itself runs in a background thread; this
    proves the HTTP response doesn't wait on it by having the mocked BFS
    block on an Event the test only sets *after* asserting the response.
    """
    release = threading.Event()

    def slow_compute(*args, **kwargs):
        release.wait(timeout=5)
        return DegreesResult(degrees=3, capped=False)

    with (
        patch(
            "backend.app.blueprints.game.service.hint_search.verify_real_article",
            return_value=VerifyResult(pageid=1, title="Some Real Article"),
        ),
        patch("backend.app.blueprints.game.service.degrees_lib.compute_degrees_live", side_effect=slow_compute),
    ):
        started = time.monotonic()
        resp = client.post("/api/game/guess", json={"guess_text": "Newto nPhysicsx"})
        elapsed = time.monotonic() - started

        assert elapsed < 2, f"guess response took {elapsed:.2f}s -- appears to have blocked on the live BFS"
        data = resp.get_json()
        assert data["guesses"][0]["degrees_pending"] is True
        assert data["guesses"][0]["degrees_value"] is None

        release.set()


def test_gibberish_guess_is_rejected_and_not_counted(client, fixture_challenge):
    with patch(
        "backend.app.blueprints.game.service.hint_search.verify_real_article",
        return_value=VerifyResult(),
    ):
        resp = client.post("/api/game/guess", json={"guess_text": "Xyzzyx Quuxfoob"})
    assert resp.status_code == 422

    state = client.get("/api/game/today").get_json()
    assert state["guesses"] == []
    assert len(state["clues_revealed"]) == 1


def test_guess_verification_failure_degrades_to_accepted_unresolved(client, fixture_challenge):
    with patch(
        "backend.app.blueprints.game.service.hint_search.verify_real_article",
        return_value=VerifyResult(unavailable=True),
    ):
        resp = client.post("/api/game/guess", json={"guess_text": "Unknow nGuessXX"})
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert data["guesses"][0]["is_correct"] is False
    assert data["guesses"][0]["degrees_value"] is None


def test_correct_guess_wins(client, fixture_challenge):
    resp = client.post("/api/game/guess", json={"guess_text": "Albert Einstein"})
    data = resp.get_json()
    assert data["status"] == "won"
    assert data["solved_answer_title"] == "Albert Einstein"
    assert data["guesses"][0]["degrees_value"] == 0
    # Won on the first guess -- only 1 of the fixture's 5 clues was ever
    # revealed, so the other 4 come back as remaining_clues (shown dimmed,
    # never used as guessing help).
    assert len(data["clues_revealed"]) == 1
    assert len(data["remaining_clues"]) == 4


def test_in_progress_game_never_gets_remaining_clues(client, fixture_challenge):
    """An in-progress game must never see clues beyond what it's earned --
    that's the entire point of the reveal-on-wrong-guess mechanic. Only a
    won game gets the rest (see test_correct_guess_wins), and never a lost
    one either, since a loss means every clue was already revealed anyway.
    """
    resp = client.post("/api/game/guess", json={"guess_text": WRONG_GUESS})
    assert resp.get_json()["status"] == "in_progress"
    assert "remaining_clues" not in resp.get_json()


def test_running_out_of_clues_loses(client, fixture_challenge):
    # Distinct guesses each attempt -- a repeated guess is rejected and
    # wouldn't advance the clue count (see test_repeating_a_previous_guess...).
    guesses = ["Wxaaaa Bxxxxxxx", "Wxbbbb Bxxxxxxx", "Wxcccc Bxxxxxxx", "Wxdddd Bxxxxxxx", "Wxeeee Bxxxxxxx"]
    with (
        patch(
            "backend.app.blueprints.game.service.hint_search.verify_real_article",
            return_value=VerifyResult(pageid=1, title="Some Real Article"),
        ),
        patch(
            "backend.app.blueprints.game.service.degrees_lib.compute_degrees_live",
            return_value=DegreesResult(degrees=None, capped=True),
        ),
    ):
        for guess in guesses:
            resp = client.post("/api/game/guess", json={"guess_text": guess})
    data = resp.get_json()
    assert data["status"] == "lost"
    assert data["solved_answer_title"] == "Albert Einstein"


def test_refresh_does_not_reshuffle_clue_order(client, fixture_challenge):
    first = client.get("/api/game/today").get_json()
    second = client.get("/api/game/today").get_json()
    assert first["clues_revealed"] == second["clues_revealed"]
