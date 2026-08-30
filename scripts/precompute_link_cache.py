#!/usr/bin/env python3
"""Precompute the degrees-of-Wikipedia link-neighborhood cache for an article.

Usage:
  precompute_link_cache.py --article-id 12 [--max-depth 4] [--node-cap 3000]

CLI wrapper around backend/app/lib/link_cache.py -- see that module's
docstring for how the precompute itself works (BFS, Wiki Replica vs API
client selection) and why it lives there rather than here: the admin
panel's "Refresh link cache" button needs the exact same logic against
the live app's own DB, not just this script.
"""

import argparse
import sys

from _db import session_scope

from backend.app.lib import link_cache
from backend.app.models.article import Article


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-id", type=int, required=True)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--node-cap", type=int, default=3000)
    args = parser.parse_args()

    client, is_replica = link_cache.make_client()
    print(f"Link source: {'Wiki Replicas (SQL)' if is_replica else 'MediaWiki API (fallback)'}")

    try:
        with session_scope() as session:
            article = session.get(Article, args.article_id)
            if not article:
                print(f"ERROR: no article with id {args.article_id}", file=sys.stderr)
                return 1

            node_count = link_cache.precompute(session, article, args.max_depth, args.node_cap, client)
            print(f"OK: cached {node_count} nodes for article_id={article.id} ({article.wiki_title})")
            return 0
    finally:
        if is_replica:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
