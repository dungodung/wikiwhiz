#!/usr/bin/env python3
"""Check the existing WikiWhiz article pool for duplicates, or list it.

Usage:
  db_check_duplicate.py --list-existing
  db_check_duplicate.py --pageid 736
  db_check_duplicate.py --title "Albert Einstein"

Exits 1 (and prints "DUPLICATE") if the given pageid/title is already in the
pool, so the content-authoring skill can skip it before doing any more work.
"""

import argparse
import json
import sys

from _db import session_scope

from backend.app.models.article import Article


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list-existing", action="store_true")
    group.add_argument("--pageid", type=int)
    group.add_argument("--title")
    args = parser.parse_args()

    with session_scope() as session:
        if args.list_existing:
            rows = session.query(Article.wiki_title, Article.wiki_pageid, Article.status).all()
            print(json.dumps([{"title": t, "pageid": p, "status": s} for t, p, s in rows], indent=2))
            return 0

        if args.pageid is not None:
            existing = session.query(Article).filter_by(wiki_pageid=args.pageid).first()
        else:
            existing = session.query(Article).filter_by(wiki_title=args.title).first()

        if existing:
            print("DUPLICATE", json.dumps({"id": existing.id, "status": existing.status}))
            return 1

        print("NOT_FOUND")
        return 0


if __name__ == "__main__":
    sys.exit(main())
