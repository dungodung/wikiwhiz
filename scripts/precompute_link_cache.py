#!/usr/bin/env python3
"""Precompute the degrees-of-Wikipedia link-neighborhood cache for an article.

Usage:
  precompute_link_cache.py --article-id 12 [--max-depth 4] [--node-cap 3000]

BFS outward from the answer article via the live MediaWiki links API
(outgoing + incoming links, treated as undirected edges), writing each
newly-discovered node into link_cache_nodes with its degree. This is the
"precompute" half of the degrees-of-Wikipedia system; backend/app/lib/degrees.py
does the "bounded live BFS fallback" half at request time for guesses that
land outside this cache.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from _db import session_scope

from backend.app.lib.mediawiki_api import MediaWikiClient
from backend.app.models.article import Article
from backend.app.models.link_cache import LinkCacheMeta, LinkCacheNode


def precompute(session, article: Article, max_depth: int, node_cap: int, client: MediaWikiClient) -> int:
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

        forward = client.links_batch(list(frontier))
        backward = client.linkshere_batch(list(frontier))
        neighbor_titles: set[str] = set()
        for pid in frontier:
            neighbor_titles |= forward.get(pid, set()) | backward.get(pid, set())

        if not neighbor_titles:
            break

        next_frontier: set[int] = set()
        titles_list = list(neighbor_titles)
        for chunk_start in range(0, len(titles_list), 50):
            chunk = titles_list[chunk_start : chunk_start + 50]
            resolved = client.query({"titles": "|".join(chunk)})
            pages = resolved.get("query", {}).get("pages", {})
            for pageid_str, page in pages.items():
                if pageid_str == "-1" or "missing" in page:
                    continue
                pageid = int(pageid_str)
                if pageid in visited:
                    continue
                visited[pageid] = depth + 1
                title_by_pageid[pageid] = page["title"]
                next_frontier.add(pageid)
                if len(visited) >= node_cap:
                    capped = True
                    break
            if capped:
                break

        frontier = next_frontier
        depth += 1

    for pageid, node_degree in visited.items():
        if node_degree == 0:
            continue
        session.add(
            LinkCacheNode(
                answer_article_id=article.id,
                node_pageid=pageid,
                node_title=title_by_pageid[pageid],
                degree=node_degree,
                discovered_via="precompute",
                computed_at=datetime.now(timezone.utc),
            )
        )

    meta.node_count = len(visited) - 1
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
    client = MediaWikiClient(user_agent)

    with session_scope() as session:
        article = session.get(Article, args.article_id)
        if not article:
            print(f"ERROR: no article with id {args.article_id}", file=sys.stderr)
            return 1

        node_count = precompute(session, article, args.max_depth, args.node_cap, client)
        print(f"OK: cached {node_count} nodes for article_id={article.id} ({article.wiki_title})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
