from datetime import date, timedelta

from backend.app.extensions import db as _db
from backend.app.lib.scheduling import schedule_article, sync_clue_order
from backend.app.lib.slot_pattern import tile_shape
from backend.app.models.clue import Clue
from backend.app.models.article import Article


def _make_article(db, title="Test Subject", pageid=500, n_clues=6):
    article = Article(
        wiki_title=title,
        wiki_pageid=pageid,
        display_title=title,
        slot_pattern=tile_shape(title),
        status="ready",
    )
    db.session.add(article)
    db.session.flush()
    for i in range(n_clues):
        db.session.add(
            Clue(
                article_id=article.id,
                clue_type="categories",
                reveal_rank_hint=i + 1,
                clue_text=f"fact {i}",
            )
        )
    db.session.flush()
    return article


def test_sync_clue_order_is_a_noop_for_an_unscheduled_article(db):
    article = _make_article(db)
    assert sync_clue_order(db.session, article) is None


def test_a_clue_added_after_scheduling_reaches_the_reveal_order(db):
    """The orphaned-clue bug: clue_order is frozen at scheduling time, so a
    clue added afterwards exists in `clues` but can never be revealed, since
    serialize_state reveals strictly from clue_order.
    """
    article = _make_article(db)
    challenge = schedule_article(db.session, article)
    db.session.flush()
    assert len(challenge.clue_order) == 6

    late = Clue(
        article_id=article.id,
        clue_type="etymology",
        reveal_rank_hint=2,
        clue_text="added after the article was already scheduled",
    )
    db.session.add(late)
    db.session.flush()

    # Without a sync the new clue is stranded outside the reveal order.
    assert late.id not in challenge.clue_order

    sync_clue_order(db.session, article)
    assert len(challenge.clue_order) == 7
    assert late.id in challenge.clue_order


def test_sync_clue_order_drops_a_deleted_clue(db):
    article = _make_article(db)
    challenge = schedule_article(db.session, article)
    db.session.flush()

    doomed_id = challenge.clue_order[0]
    db.session.delete(db.session.get(Clue, doomed_id))
    db.session.flush()

    sync_clue_order(db.session, article)
    assert doomed_id not in challenge.clue_order
    assert len(challenge.clue_order) == 5


def test_sync_clue_order_is_stable_when_the_clue_set_is_unchanged(db):
    """Re-seeded from the challenge id, so repeated syncs must not reshuffle
    the day -- otherwise touching any clue would silently reorder the rest.
    """
    article = _make_article(db)
    challenge = schedule_article(db.session, article)
    db.session.flush()
    before = list(challenge.clue_order)

    sync_clue_order(db.session, article)
    sync_clue_order(db.session, article)
    assert challenge.clue_order == before


def test_sync_clue_order_excludes_title_leaking_clues(db):
    article = _make_article(db)
    challenge = schedule_article(db.session, article)
    db.session.flush()

    leaky = Clue(
        article_id=article.id,
        clue_type="etymology",
        reveal_rank_hint=1,
        clue_text="mentions Test Subject outright",
        is_title_leaking=True,
    )
    db.session.add(leaky)
    db.session.flush()

    sync_clue_order(db.session, article)
    assert leaky.id not in challenge.clue_order
    assert len(challenge.clue_order) == 6
