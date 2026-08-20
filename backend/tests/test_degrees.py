from unittest.mock import MagicMock, patch

import pymysql
import requests

from backend.app.extensions import db
from backend.app.lib.degrees import compute_degrees_live, resolve_and_score_guess
from backend.app.models.article import Article
from backend.app.models.link_cache import LinkCacheNode


def _make_article(db):
    article = Article(
        wiki_title="Albert Einstein",
        wiki_pageid=736,
        display_title="Albert Einstein",
        slot_pattern="L" * 14,
        status="ready",
    )
    db.session.add(article)
    db.session.flush()
    return article


def test_guess_matching_a_cached_node_resolves_with_its_degree(app, db):
    with app.app_context():
        article = _make_article(db)
        db.session.add(
            LinkCacheNode(
                answer_article_id=article.id,
                node_pageid=999,
                node_title="Isaac Newton In",  # contrived but same 14-letter tile count
                node_tiles="isaacnewtonin",
                degree=2,
            )
        )
        db.session.commit()

        result = resolve_and_score_guess(article.id, "IsaacNewtonIn")

        assert result is not None
        assert result.pageid == 999
        assert result.degrees_result.degrees == 2
        assert result.degrees_result.capped is False


def test_guess_lookup_is_case_insensitive(app, db):
    with app.app_context():
        article = _make_article(db)
        db.session.add(
            LinkCacheNode(
                answer_article_id=article.id,
                node_pageid=999,
                node_title="Someother Title",
                node_tiles="someothertitle",
                degree=3,
            )
        )
        db.session.commit()

        result = resolve_and_score_guess(article.id, "SOMEOTHERTITLE")

        assert result is not None
        assert result.degrees_result.degrees == 3


def test_guess_not_in_cache_degrades_to_not_found(app, db):
    """A guess that spells no known same-shape neighbor -- either because no
    such real article exists, or it's further from the answer than the
    precompute's depth/node cap reached -- must never raise, just report
    'not found nearby'.
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        result = resolve_and_score_guess(article.id, "NoSuchArticle")

        assert result is None


def test_compute_degrees_live_same_article_is_zero(app, db):
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        result = compute_degrees_live(MagicMock(), article, article.wiki_pageid, depth_cap=6, node_cap=100, timeout_sec=1)

        assert result.degrees == 0
        assert result.capped is False


def test_compute_degrees_live_finds_a_one_hop_connection_and_caches_it(app, db):
    """Regression test: a real report that a genuinely close, well-known
    pair (Albert Einstein <-> George H. W. Bush, 2 real hops apart) was
    coming back "not found nearby" because the tile-based-guessing redesign
    dropped the live BFS fallback entirely, relying only on the bounded
    precomputed cache. This is the reinstated fallback: a guess confirmed
    real but missing from the cache gets one bounded live BFS attempt.
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        client = MagicMock()
        client.links_batch.return_value = {article.wiki_pageid: {"George H W Bush"}}
        client.linkshere_batch.return_value = {article.wiki_pageid: set()}
        client.titles_to_pageids.return_value = {"George H W Bush": 200}
        client.pageids_to_titles.return_value = {200: "George H W Bush"}

        result = compute_degrees_live(client, article, 200, depth_cap=6, node_cap=100, timeout_sec=4)

        assert result.degrees == 1
        assert result.capped is False

        cached = LinkCacheNode.query.filter_by(answer_article_id=article.id, node_pageid=200).first()
        assert cached is not None
        assert cached.node_tiles == "george h w bush"
        assert cached.degree == 1


def test_compute_degrees_live_resolves_all_neighbors_past_the_first_50(app, db):
    """Regression test: an earlier version only ever resolved the first 50
    of a node's neighbor titles to pageids (an unchunked `[:50]` slice) and
    silently dropped the rest -- for a hub-like answer article (hundreds of
    links each way is normal for a notable person), this could and did miss
    a real, well-known connection just because the intermediate page wasn't
    in that arbitrary first slice. Here the shared neighbor is the 60th
    (0-indexed 59th) title, past the old single-chunk boundary. The actual
    50-per-call chunking now lives inside MediaWikiClient.titles_to_pageids
    (see test_mediawiki_api.py) -- this test locks in that
    _live_bidirectional_bfs hands the *entire* neighbor set to that method
    in one call, rather than truncating before ever calling it.
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        titles = [f"Filler Title {i}" for i in range(59)] + ["George H W Bush"]
        client = MagicMock()
        client.links_batch.return_value = {article.wiki_pageid: set(titles)}
        client.linkshere_batch.return_value = {article.wiki_pageid: set()}
        pid_by_title = {title: 1000 + i for i, title in enumerate(titles)}
        pid_by_title["George H W Bush"] = 200
        client.titles_to_pageids.return_value = pid_by_title
        client.pageids_to_titles.return_value = {200: "George H W Bush"}

        result = compute_degrees_live(client, article, 200, depth_cap=6, node_cap=1000, timeout_sec=4)

        assert result.degrees == 1
        assert result.capped is False
        # The full 60-title neighbor set was handed off in a single call --
        # nothing was truncated before it ever reached titles_to_pageids.
        ((called_titles,), _kwargs) = client.titles_to_pageids.call_args
        assert len(called_titles) == 60


def test_compute_degrees_live_finds_a_two_hop_connection_via_title_shortcut(app, db):
    """Regression test: resolving every newly-discovered neighbor *title* to
    a pageid before checking for an intersection made a 2-hop connection
    between two hub-like articles (hundreds of links each way) take 20-30+
    seconds live, and could still miss the timeout entirely. The fix checks
    for a plain title-string match against the other side's already-resolved
    titles first -- this test locks in that once side A has fully resolved
    its neighborhood, a match among side B's *raw*, unresolved neighbor
    titles is found without a second full resolution pass.
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        title_by_pid = {501: "Node A", 502: "Node B", 503: "Node C", 504: "Node D", 505: "Shared Node"}
        pid_by_title = {v: k for k, v in title_by_pid.items()}

        client = MagicMock()
        client.links_batch.side_effect = lambda pageids, **kwargs: (
            {article.wiki_pageid: set(title_by_pid.values())} if article.wiki_pageid in pageids else {999: {"Shared Node"}}
        )
        client.linkshere_batch.return_value = {}
        client.titles_to_pageids.return_value = pid_by_title
        client.pageids_to_titles.return_value = title_by_pid

        result = compute_degrees_live(client, article, 999, depth_cap=6, node_cap=1000, timeout_sec=4)

        assert result.degrees == 2
        assert result.capped is False
        # One resolution call for side A's 5 titles, one single-title
        # shortcut lookup, and one opportunistic-cache pageids lookup
        # afterward -- never a full resolution pass for side B's own
        # (potentially huge) neighborhood.
        assert client.titles_to_pageids.call_count == 2
        assert client.pageids_to_titles.call_count == 1


def test_compute_degrees_live_prefers_a_reachable_replica_over_the_api(app, db):
    """When wiki_replica.get_client() returns a usable client, the BFS must
    run against it instead of the MediaWiki API client -- the API client is
    only ever the fallback for when no replica is reachable, which is the
    default on this dev machine (proven by every other test in this file,
    where get_client() naturally returns None since ~/replica.my.cnf doesn't
    exist here).
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        replica = MagicMock()
        replica.links_batch.return_value = {article.wiki_pageid: {"George H W Bush"}}
        replica.linkshere_batch.return_value = {article.wiki_pageid: set()}
        replica.titles_to_pageids.return_value = {"George H W Bush": 200}
        replica.pageids_to_titles.return_value = {200: "George H W Bush"}

        api_client = MagicMock()

        with patch("backend.app.lib.degrees.wiki_replica.get_client", return_value=replica):
            result = compute_degrees_live(api_client, article, 200, depth_cap=6, node_cap=100, timeout_sec=4)

        assert result.degrees == 1
        api_client.links_batch.assert_not_called()
        api_client.linkshere_batch.assert_not_called()
        api_client.titles_to_pageids.assert_not_called()
        replica.close.assert_called_once()


def test_compute_degrees_live_degrades_gracefully_on_replica_failure_without_falling_back_mid_run(app, db):
    """A replica that connects successfully (get_client() returns a client)
    but then fails mid-BFS (a query raises) degrades exactly like a live-API
    failure does -- 'not found nearby', not a raised exception. This does
    NOT retry the same guess against the API client afterward: a connection
    that just passed get_client()'s liveness probe failing again within the
    same request is treated as a rare edge case for v1, not a signal to
    silently redo the whole bounded BFS against a second backend.
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        replica = MagicMock()
        replica.links_batch.side_effect = pymysql.err.OperationalError("replica connection lost")

        api_client = MagicMock()

        with patch("backend.app.lib.degrees.wiki_replica.get_client", return_value=replica):
            result = compute_degrees_live(api_client, article, 200, depth_cap=6, node_cap=100, timeout_sec=4)

        assert result.degrees is None
        assert result.capped is True
        api_client.links_batch.assert_not_called()
        replica.close.assert_called_once()


def test_compute_degrees_live_degrades_gracefully_on_network_failure(app, db):
    """Regression test: a transient MediaWiki API failure during the live
    BFS must not raise out of compute_degrees_live -- the guess endpoint has
    to be able to keep responding with a degraded result.
    """
    with app.app_context():
        article = _make_article(db)
        db.session.commit()

        client = MagicMock()
        client.links_batch.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")

        result = compute_degrees_live(client, article, 999, depth_cap=6, node_cap=100, timeout_sec=1)

        assert result.degrees is None
        assert result.capped is True
