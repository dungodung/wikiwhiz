"""Degrees of Wikipedia: shortest link-path between a guessed article and the
answer article.

Cache hit against LinkCacheNode.node_tiles (populated ahead of time by
scripts/precompute_link_cache.py, which BFS-walks the real link graph and
keeps only same-total-tile-count neighbors) -> instant answer, no API call.

Cache miss -> once game/service.py has confirmed via a live search that the
guess spells *some* real article (see hint_search.verify_real_article), this
falls back to a bounded bidirectional BFS, capped by depth/node-count/
wall-clock time so a single guess can never hang the request. This was cut
during the tile-based-guessing redesign on the assumption the precomputed
cache would be "good enough" -- live testing against a real article pair
(Albert Einstein <-> George H. W. Bush, genuinely 2 hops apart) showed that
assumption was wrong: plenty of real, well-known connections fall outside
whatever radius the precompute happened to cover, and reporting those as
"not found nearby" is a materially worse answer than the live BFS would give.
Newly-visited same-shape nodes from a live run are opportunistically written
back into the cache so repeat or nearby guesses don't re-pay the cost.

The BFS itself (_live_bidirectional_bfs below) is written against a
duck-typed link-source contract -- links_batch/linkshere_batch/
titles_to_pageids/pageids_to_titles, all with identical signatures on both
implementations -- so it can run against either backend without caring which:
wiki_replica.WikiReplicaClient (a direct SQL connection to Wikimedia's Wiki
Replicas, only reachable from Toolforge) when available, since a single
indexed JOIN there is dramatically cheaper than the paginated MediaWiki
Action API this module used exclusively before; MediaWikiClient (this same
live API) as the fallback otherwise -- always, on a local dev machine, and
on Toolforge only if the replica is unreachable. compute_degrees_live below
is the single place that chooses between them, via wiki_replica.get_client().

Known limitation: when *both* the answer and the guess are hub-like articles
(hundreds of links each way -- true of most famous people), even the
title-shortcut in _live_bidirectional_bfs can fail to find a real,
close connection within the time/node budget. Wikipedia's heavy use of
redirects means the same target page is often linked to via different
literal text from each side (a canonical title from one, a redirect from
the other), so the plain string-based shortcut doesn't always catch it, and
falling through to full pageid resolution for a genuine hub is expensive
regardless. A dedicated graph index (which is how reference tools like
sixdegreesofwikipedia.com answer near-instantly) would solve this properly;
live per-guess API calls are a reasonable approximation for the common case,
not a full substitute for one.
"""

import logging
from datetime import datetime, timezone

import pymysql
import requests

from ..extensions import db
from ..models.article import Article
from ..models.link_cache import LinkCacheNode
from . import wiki_replica
from .mediawiki_api import MediaWikiClient, now
from .slot_pattern import normalize_to_tiles

logger = logging.getLogger(__name__)

MAX_OPPORTUNISTIC_CACHE_WRITES = 500


class DegreesResult:
    def __init__(self, degrees: int | None, capped: bool):
        self.degrees = degrees
        self.capped = capped


class ResolvedGuess:
    def __init__(self, pageid: int, title: str, degrees_result: DegreesResult):
        self.pageid = pageid
        self.title = title
        self.degrees_result = degrees_result


def resolve_and_score_guess(answer_article_id: int, guess_tiles: str) -> ResolvedGuess | None:
    """guess_tiles: the player's filled-in tile string, already validated to
    be the right length and character set by the caller. Returns None if no
    real article in the precomputed neighborhood spells out these exact
    tiles (case-insensitive) -- the caller falls back to a live lookup (see
    compute_degrees_live) before giving up on a degrees value.
    """
    node = LinkCacheNode.query.filter_by(
        answer_article_id=answer_article_id, node_tiles=guess_tiles.lower()
    ).first()
    if node is None:
        return None
    return ResolvedGuess(
        pageid=node.node_pageid,
        title=node.node_title,
        degrees_result=DegreesResult(degrees=node.degree, capped=False),
    )


def _live_bidirectional_bfs(
    client: MediaWikiClient,
    start_pageid: int,
    goal_pageid: int,
    depth_cap: int,
    node_cap: int,
    timeout_sec: float,
) -> tuple[int | None, dict[int, int], dict[int, int]]:
    """Alternates expanding the smaller frontier outward from both ends.

    Returns (degrees_or_None, visited_from_start, visited_from_goal) so the
    caller can opportunistically cache newly-discovered nodes relative to the
    answer article.

    A hub-like article (any well-known person easily has several hundred
    links each way) makes the naive version of this expensive: resolving
    every newly-discovered neighbor *title* to a pageid, chunked at the
    API's 50-per-call limit, can mean dozens of round trips per side per
    round. Before paying for that, this checks for a plain title-string
    intersection between the side that's expanding and the *other* side's
    already-resolved titles -- cheap, in-memory, no API call. Confirmed live
    against a real 2-hop pair (Albert Einstein <-> George H. W. Bush) that
    this cuts the time to find the connection from 20-30+ seconds down to a
    few: side A fully resolves its ~1-hop neighborhood once, and from then
    on side B's *raw* neighbor titles (before any resolution) are checked
    against it first, so the shared node is usually found without needing
    to resolve most of side B's own large neighborhood at all.

    Each side tracks its own hop count (depth_a/depth_b) rather than a
    single shared counter -- with "expand the smaller frontier" alternation,
    the two sides don't take turns 1:1 (a side with a much smaller frontier
    can get expanded several rounds in a row before the other catches up),
    so a shared counter mislabels a side's Nth hop with however many total
    rounds have elapsed instead of N, inflating the reported degrees.
    """
    if start_pageid == goal_pageid:
        return 0, {start_pageid: 0}, {}

    deadline = now() + timeout_sec
    visited_a: dict[int, int] = {start_pageid: 0}
    visited_b: dict[int, int] = {goal_pageid: 0}
    titles_a: dict[str, int] = {}
    titles_b: dict[str, int] = {}
    frontier_a = {start_pageid}
    frontier_b = {goal_pageid}
    depth_a = 0
    depth_b = 0

    while frontier_a and frontier_b and now() < deadline:
        if len(visited_a) + len(visited_b) >= node_cap:
            break
        if depth_a >= depth_cap and depth_b >= depth_cap:
            break

        # Expand the smaller frontier first -- keeps branching factor down
        # -- unless that side has already hit its own depth cap, in which
        # case keep pushing the other side while it still has budget.
        expand_a = len(frontier_a) <= len(frontier_b)
        if expand_a and depth_a >= depth_cap:
            expand_a = False
        elif not expand_a and depth_b >= depth_cap:
            expand_a = True

        frontier = frontier_a if expand_a else frontier_b
        visited_this = visited_a if expand_a else visited_b
        visited_other = visited_b if expand_a else visited_a
        titles_this = titles_a if expand_a else titles_b
        titles_other = titles_b if expand_a else titles_a
        this_depth = (depth_a if expand_a else depth_b) + 1

        # Bounded to a handful of continuation pages -- an unbounded hub
        # article (a landmark linked from thousands of "list of..." pages)
        # in the frontier could otherwise stall a single round well past
        # `deadline` below, since that check only runs *between* rounds.
        forward = client.links_batch(list(frontier), max_continuation_pages=8)
        backward = client.linkshere_batch(list(frontier), max_continuation_pages=8)
        all_neighbor_titles: set[str] = set()
        for pid in frontier:
            all_neighbor_titles |= forward.get(pid, set()) | backward.get(pid, set())

        # Cheap shortcut: a title the other side already resolved, found
        # among this side's *raw* (unresolved) neighbors, is the connection
        # -- one single-title lookup confirms its pageid, no need to resolve
        # anything else this round.
        shortcut_hits = all_neighbor_titles & titles_other.keys()
        if shortcut_hits:
            hit_title = next(iter(shortcut_hits))
            hit_pid = client.titles_to_pageids([hit_title]).get(hit_title)
            if hit_pid is not None:
                visited_this[hit_pid] = this_depth
                return this_depth + titles_other[hit_title], visited_a, visited_b

        # No shortcut -- resolve everything to keep expanding. An earlier
        # version silently took only the first 50 titles total per node and
        # dropped the rest, which meant a real connection could go
        # undiscovered simply because the intermediate page happened to be
        # outside that arbitrary first slice -- confirmed live, not
        # theoretical. titles_to_pageids chunks internally and resolves the
        # full set.
        next_frontier: set[int] = set()
        found_total: int | None = None
        titles_list = list(all_neighbor_titles)
        resolved = client.titles_to_pageids(titles_list)
        for neighbor_title, neighbor_pid in resolved.items():
            if neighbor_pid in visited_this:
                continue
            visited_this[neighbor_pid] = this_depth
            titles_this[neighbor_title] = this_depth
            next_frontier.add(neighbor_pid)
            if neighbor_pid in visited_other:
                found_total = this_depth + visited_other[neighbor_pid]

        if found_total is not None:
            return found_total, visited_a, visited_b

        if expand_a:
            frontier_a = next_frontier
            depth_a += 1
        else:
            frontier_b = next_frontier
            depth_b += 1

    return None, visited_a, visited_b


def _opportunistically_cache(
    answer_article: Article, visited_from_answer: dict[int, int], client: MediaWikiClient
) -> None:
    """Writes newly-discovered nodes back to LinkCacheNode, same-shape filter
    and node_tiles included -- mirrors scripts/precompute_link_cache.py so a
    node written here is indistinguishable from one the precompute found.
    """
    items = list(visited_from_answer.items())[:MAX_OPPORTUNISTIC_CACHE_WRITES]
    if not items:
        return
    answer_tile_count = len(normalize_to_tiles(answer_article.display_title))

    pageids = [pid for pid, _ in items]
    title_by_pageid = client.pageids_to_titles(pageids)

    for pageid, degree in items:
        if degree == 0:
            continue
        title = title_by_pageid.get(pageid)
        if not title:
            continue
        node_tiles = normalize_to_tiles(title)
        if len(node_tiles) != answer_tile_count:
            continue
        existing = LinkCacheNode.query.filter_by(
            answer_article_id=answer_article.id, node_pageid=pageid
        ).first()
        if existing:
            continue
        db.session.add(
            LinkCacheNode(
                answer_article_id=answer_article.id,
                node_pageid=pageid,
                node_title=title,
                node_tiles=node_tiles.lower(),
                degree=degree,
                discovered_via="live_bfs",
                computed_at=datetime.now(timezone.utc),
            )
        )
    db.session.commit()


def compute_degrees_live(
    client: MediaWikiClient,
    answer_article: Article,
    guess_pageid: int,
    depth_cap: int,
    node_cap: int,
    timeout_sec: float,
) -> DegreesResult:
    """Only called after the guess has already been confirmed to spell a
    real article and the precomputed cache missed it (see
    game/service.py::_resolve_wrong_guess) -- this is the bounded live
    fallback for that case, not a general-purpose lookup.

    `client` (a MediaWikiClient) is always required and always available --
    it's the guaranteed fallback. Wiki Replicas access, when reachable, is
    preferred instead: replica.get_client() is called once here (not once
    per network round-trip inside the BFS, which would multiply a down
    replica's connect-timeout penalty by however many rounds the BFS takes),
    so the worst case for an unreachable replica is a single short connect
    timeout, not a slower-than-baseline guess.
    """
    replica = wiki_replica.get_client()
    active_client = replica or client
    try:
        try:
            degrees, visited_a, _visited_b = _live_bidirectional_bfs(
                active_client,
                start_pageid=answer_article.wiki_pageid,
                goal_pageid=guess_pageid,
                depth_cap=depth_cap,
                node_cap=node_cap,
                timeout_sec=timeout_sec,
            )
        except (requests.RequestException, pymysql.MySQLError):
            logger.warning("Live degrees BFS failed for answer_article_id=%s", answer_article.id, exc_info=True)
            return DegreesResult(degrees=None, capped=True)

        try:
            _opportunistically_cache(answer_article, visited_a, active_client)
        except (requests.RequestException, pymysql.MySQLError):
            logger.warning(
                "Opportunistic link-cache write failed for answer_article_id=%s", answer_article.id, exc_info=True
            )
            db.session.rollback()
    finally:
        if replica is not None:
            replica.close()

    if degrees is None:
        return DegreesResult(degrees=None, capped=True)
    return DegreesResult(degrees=degrees, capped=False)
