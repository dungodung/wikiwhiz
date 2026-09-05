from backend.app.extensions import db as db_ext
from backend.app.lib.link_cache import precompute
from backend.app.models.article import Article
from backend.app.models.link_cache import LinkCacheNode


class _FakeClient:
    """Minimal duck-typed stand-in for MediaWikiClient/WikiReplicaClient,
    covering just the calls precompute() makes.
    """

    def __init__(self, forward, backward, pageids, redirects):
        self._forward = forward
        self._backward = backward
        self._pageids = pageids
        self._redirects = redirects

    def links_batch(self, pageids, **kwargs):
        return {pid: self._forward.get(pid, set()) for pid in pageids}

    def linkshere_batch(self, pageids, **kwargs):
        return {pid: self._backward.get(pid, set()) for pid in pageids}

    def titles_to_pageids(self, titles):
        return {t: self._pageids[t] for t in titles if t in self._pageids}

    def redirects_to(self, pageid, title):
        return self._redirects


def _make_article(db):
    article = Article(
        wiki_title="Colosseum",
        wiki_pageid=49603,
        display_title="Colosseum",
        slot_pattern="L" * 9,
        status="ready",
    )
    db.session.add(article)
    db.session.flush()
    return article


def test_precompute_excludes_a_redirect_to_the_answer_itself(app, db):
    """Regression test: a same-shape neighbor that's actually a redirect to
    the answer (e.g. "Colloseum" -> "Colosseum") must not be cached as a
    distinct wrong-guess node -- titles_to_pageids resolves it to its own
    pageid, not the answer's, which previously caused a guess spelling it
    to be rejected instead of accepted as correct. See game/service.py's
    redirect-to-answer handling and hint_search.verify_real_article, which
    correctly recognize this guess once it isn't shadowed by a stale cache
    hit.
    """
    article = _make_article(db)
    client = _FakeClient(
        forward={49603: set()},
        backward={49603: {"Colloseum", "Fictional"}},
        pageids={"Colloseum": 284813, "Fictional": 555},
        redirects={"Colloseum"},
    )

    kept = precompute(db_ext.session, article, max_depth=1, node_cap=100, client=client)

    nodes = LinkCacheNode.query.filter_by(answer_article_id=article.id).all()
    titles = {n.node_title for n in nodes}
    assert "Colloseum" not in titles
    assert "Fictional" in titles
    assert kept == 1
