#!/usr/bin/env python3
"""Precompute the degrees-of-Wikipedia link-neighborhood cache for an article.

Usage:
  precompute_link_cache.py --article-id 12 [--max-depth 4] [--node-cap 3000]

BFS outward from the answer article (outgoing + incoming links, treated as
undirected edges), writing each newly-discovered node into link_cache_nodes
with its degree. This is the "precompute" half of the degrees-of-Wikipedia
system; backend/app/lib/degrees.py does the "bounded live BFS fallback" half
at request time for guesses that land outside this cache.

Prefers Wikimedia's Wiki Replicas (direct SQL, only reachable from Toolforge
-- see backend/app/lib/wiki_replica.py) over the live MediaWiki Action API
when available, since a hub-like answer article's link neighborhood is a
single indexed JOIN there instead of hundreds of sequential paginated API
calls. Falls back to the API automatically otherwise -- always, on a local
dev machine.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from _db import session_scope

from backend.app.lib import wiki_replica
from backend.app.lib.mediawiki_api import MediaWikiClient
from backend.app.lib.slot_pattern import normalize_to_tiles
from backend.app.models.article import Article
from backend.app.models.link_cache import LinkCacheMeta, LinkCacheNode


def precompute(session, article: Article, max_depth: int, node_cap: int, client: MediaWikiClient) -> int:
    # Only same-total-length titles can ever fill this article's fixed tile
    # board, so only those are useful degrees-of-Wikipedia candidates -- see
    # lib/slot_pattern.py and lib/degrees.py. The BFS still walks through
    # differently-shaped articles as stepping stones; this just filters what
    # gets written to link_cache_nodes.
    answer_tile_count = len(normalize_to_tiles(article.display_title))
    session.query(LinkCacheNode).filter_by(answer_article_id=article.id).delete()
    meta = session.get(LinkCacheMeta, article.id) or LinkCacheMeta(answer_article_id=article.id)
    meta.max_depth_precomputed = max_depth
    meta.node_cap = node_cap
    meta.status = "pending"
    session.merge(meta)
    session.flush()

    visited: dict[int, int] = {article.wiki_pageid: 0}
    title_by_pageid: dict[int, str] = {article.wiki_pageid: article.wiki_title}
    frontier = {article.wiki_pageid}
    depth = 0
    capped = False

    while frontier and depth < max_depth:
        if len(visited) >= node_cap:
            capped = True
            break

        # Bounded to a handful of continuation pages per batch -- an
        # unbounded hub article (a landmark linked from thousands of "list
        # of..." pages) entering the frontier can otherwise turn one BFS
        # round into hundreds of sequential API round-trips, effectively
        # hanging the whole precompute run. Confirmed live: the Eiffel
        # Tower run stalled for 15+ minutes with almost no CPU time used
        # (i.e. waiting on network, not computing) before this fix.
        forward = client.links_batch(list(frontier), max_continuation_pages=20)
        backward = client.linkshere_batch(list(frontier), max_continuation_pages=20)
        neighbor_titles: set[str] = set()
        for pid in frontier:
            neighbor_titles |= forward.get(pid, set()) | backward.get(pid, set())

        if not neighbor_titles:
            break

        next_frontier: set[int] = set()
        titles_list = list(neighbor_titles)
        resolved = client.titles_to_pageids(titles_list)
        for title, pageid in resolved.items():
            if pageid in visited:
                continue
            visited[pageid] = depth + 1
            title_by_pageid[pageid] = title
            next_frontier.add(pageid)
            if len(visited) >= node_cap:
                capped = True
                break

        frontier = next_frontier
        depth += 1

    kept = 0
    for pageid, node_degree in visited.items():
        if node_degree == 0:
            continue
        node_title = title_by_pageid[pageid]
        node_tiles = normalize_to_tiles(node_title)
        if len(node_tiles) != answer_tile_count:
            continue
        session.add(
            LinkCacheNode(
                answer_article_id=article.id,
                node_pageid=pageid,
                node_title=node_title,
                node_tiles=node_tiles.lower(),
                degree=node_degree,
                discovered_via="precompute",
                computed_at=datetime.now(timezone.utc),
            )
        )
        kept += 1

    meta.node_count = kept
    meta.status = "capped" if capped else "complete"
    meta.computed_at = datetime.now(timezone.utc)
    session.merge(meta)

    return meta.node_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-id", type=int, required=True)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--node-cap", type=int, default=3000)
    args = parser.parse_args()

    user_agent = os.environ.get("WIKIWHIZ_USER_AGENT", "WikiWhiz/0.1 (content-authoring script) requests")
    api_client = MediaWikiClient(user_agent)
    replica_client = wiki_replica.get_client()
    client = replica_client or api_client
    print(f"Link source: {'Wiki Replicas (SQL)' if replica_client else 'MediaWiki API (fallback)'}")

    try:
        with session_scope() as session:
            article = session.get(Article, args.article_id)
            if not article:
                print(f"ERROR: no article with id {args.article_id}", file=sys.stderr)
                return 1

            node_count = precompute(session, article, args.max_depth, args.node_cap, client)
            print(f"OK: cached {node_count} nodes for article_id={article.id} ({article.wiki_title})")
            return 0
    finally:
        if replica_client is not None:
            replica_client.close()


if __name__ == "__main__":
    sys.exit(main())
