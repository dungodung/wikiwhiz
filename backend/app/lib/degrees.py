"""Degrees of Wikipedia: shortest link-path between a guessed article and the
answer article.

Cache hit in link_cache_nodes (seeded by the content-authoring skill's
precompute_link_cache.py, depth ~3-4 from the answer) -> instant answer.
Cache miss -> bounded bidirectional BFS over the live MediaWiki links API,
capped by depth/node-count/wall-clock time so a single guess can never hang
the request. Newly-visited nodes from a live run are opportunistically written
back into the cache so repeat or nearby guesses don't re-pay the cost.
"""

import logging
from datetime import datetime, timezone

import requests

from ..extensions import db
from ..models.article import Article
from ..models.link_cache import LinkCacheNode
from .mediawiki_api import MediaWikiClient, now

logger = logging.getLogger(__name__)

MAX_OPPORTUNISTIC_CACHE_WRITES = 500


class DegreesResult:
    def __init__(self, degrees: int | None, capped: bool):
        self.degrees = degrees
        self.capped = capped


def _cache_lookup(answer_article_id: int, guess_pageid: int) -> int | None:
    row = LinkCacheNode.query.filter_by(
        answer_article_id=answer_article_id, node_pageid=guess_pageid
    ).first()
    return row.degree if row else None


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
    """
    if start_pageid == goal_pageid:
        return 0, {start_pageid: 0}, {}

    deadline = now() + timeout_sec
    visited_a: dict[int, int] = {start_pageid: 0}
    visited_b: dict[int, int] = {goal_pageid: 0}
    frontier_a = {start_pageid}
    frontier_b = {goal_pageid}

    depth = 0
    while frontier_a and frontier_b and depth < depth_cap and now() < deadline:
        if len(visited_a) + len(visited_b) >= node_cap:
            break

        # Expand the smaller frontier first -- keeps branching factor down.
        expand_a = len(frontier_a) <= len(frontier_b)
        frontier = frontier_a if expand_a else frontier_b
        visited_this = visited_a if expand_a else visited_b
        visited_other = visited_b if expand_a else visited_a

        forward = client.links_batch(list(frontier))
        backward = client.linkshere_batch(list(frontier))
        # Need pageids for backward-linking titles too; resolve via a follow-up
        # query only for titles not already known -- kept simple by just using
        # forward links (outgoing) union incoming title strings resolved lazily.
        next_frontier: set[int] = set()
        for pid in frontier:
            neighbor_titles = forward.get(pid, set()) | backward.get(pid, set())
            if not neighbor_titles:
                continue
            resolved = client.query(
                {
                    "titles": "|".join(list(neighbor_titles)[:50]),
                }
            )
            pages = resolved.get("query", {}).get("pages", {})
            for neighbor_pid_str, page in pages.items():
                if neighbor_pid_str == "-1" or "missing" in page:
                    continue
                neighbor_pid = int(neighbor_pid_str)
                if neighbor_pid in visited_this:
                    continue
                visited_this[neighbor_pid] = depth + 1
                next_frontier.add(neighbor_pid)
                if neighbor_pid in visited_other:
                    total = visited_this[neighbor_pid] + visited_other[neighbor_pid]
                    if expand_a:
                        return total, visited_a, visited_b
                    return total, visited_a, visited_b

        if expand_a:
            frontier_a = next_frontier
        else:
            frontier_b = next_frontier
        depth += 1

    return None, visited_a, visited_b


def _opportunistically_cache(answer_article_id: int, visited_from_answer: dict[int, int], client: MediaWikiClient) -> None:
    items = list(visited_from_answer.items())[:MAX_OPPORTUNISTIC_CACHE_WRITES]
    if not items:
        return
    pageids = [pid for pid, _ in items]
    titles_resp = client.query({"pageids": "|".join(str(p) for p in pageids)})
    pages = titles_resp.get("query", {}).get("pages", {})
    title_by_pageid = {int(pid): page["title"] for pid, page in pages.items() if "missing" not in page}

    for pageid, degree in items:
        title = title_by_pageid.get(pageid)
        if not title:
            continue
        existing = LinkCacheNode.query.filter_by(
            answer_article_id=answer_article_id, node_pageid=pageid
        ).first()
        if existing:
            continue
        db.session.add(
            LinkCacheNode(
                answer_article_id=answer_article_id,
                node_pageid=pageid,
                node_title=title,
                degree=degree,
                discovered_via="live_bfs",
                computed_at=datetime.now(timezone.utc),
            )
        )
    db.session.commit()


def compute_degrees(
    client: MediaWikiClient,
    answer_article: Article,
    guess_pageid: int,
    depth_cap: int,
    node_cap: int,
    timeout_sec: float,
) -> DegreesResult:
    if guess_pageid == answer_article.wiki_pageid:
        return DegreesResult(degrees=0, capped=False)

    cached = _cache_lookup(answer_article.id, guess_pageid)
    if cached is not None:
        return DegreesResult(degrees=cached, capped=False)

    # The live BFS depends on the MediaWiki API being reachable, which it
    # sometimes isn't (rate limits, transient 5xx, network blips). A guess
    # must never 500 just because this best-effort lookup failed -- degrade
    # to "not found nearby" instead, same as exhausting the depth/node caps.
    try:
        degrees, visited_a, _visited_b = _live_bidirectional_bfs(
            client,
            start_pageid=answer_article.wiki_pageid,
            goal_pageid=guess_pageid,
            depth_cap=depth_cap,
            node_cap=node_cap,
            timeout_sec=timeout_sec,
        )
    except requests.RequestException:
        logger.warning("Live degrees BFS failed for answer_article_id=%s", answer_article.id, exc_info=True)
        return DegreesResult(degrees=None, capped=True)

    try:
        _opportunistically_cache(answer_article.id, visited_a, client)
    except requests.RequestException:
        logger.warning("Opportunistic link-cache write failed for answer_article_id=%s", answer_article.id, exc_info=True)
        db.session.rollback()

    if degrees is None:
        return DegreesResult(degrees=None, capped=True)
    return DegreesResult(degrees=degrees, capped=False)
