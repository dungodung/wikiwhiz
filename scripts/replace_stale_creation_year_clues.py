#!/usr/bin/env python3
"""One-off content maintenance: replace "This Wikipedia article was created
in <year>" clues on every article scheduled from a given date onward with a
real fact about the subject. Such clues are now only allowed for articles
created in 2020 or later (see clue_guard.is_stale_creation_year).

Each swap replaces the clue's type+text in place; the clue's id and its slot
in daily_challenges.clue_order are unchanged, so no reveal-order
recomputation is needed (same approach as refresh_facts_over_stats.py).

Replacements are keyed by the article's wiki_pageid rather than clue id, so
the same table applies to any database the pool has been synced to. Any
stale clue found without a replacement is listed and the run aborts before
writing anything -- add an entry to REPLACEMENTS and re-run.

Usage:
  replace_stale_creation_year_clues.py [--from-date 2026-10-11]
      apply to the database .env points at
  replace_stale_creation_year_clues.py --emit-sql > fix.sql
      print every REPLACEMENTS entry as an UPDATE keyed by pageid, without
      touching any database, for production ToolsDB (reached via the
      bastion's mariadb client, see docs/deployment-toolforge.md). Unlike
      the default mode this can't detect clues missing a replacement, so
      first check production with the SELECT printed at the top.

Safe to re-run: an already-replaced clue no longer matches.
"""

import argparse
import sys
from datetime import date, timedelta

from _db import session_scope

from backend.app.lib.clue_guard import is_stale_creation_year, leaks_title
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge

# wiki_pageid -> (new_type, new_text); reveal_rank_hint is kept as-is
REPLACEMENTS = {
    # Serena Williams
    164910: ("dyk_or_notable_fact", "Away from her main career, this person trained and qualified as a certified nail technician."),
    # Chernobyl disaster
    2589713: ("etymology", "The town this event is named after takes its name from the local word for mugwort, a bitter wild herb that grows in the region."),
}


def _sql_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-date", type=date.fromisoformat, default=date.today() + timedelta(days=1))
    parser.add_argument("--emit-sql", action="store_true")
    args = parser.parse_args()

    if args.emit_sql:
        print(
            f"-- Check first: any row here without a matching UPDATE below still needs a replacement.\n"
            f"-- SELECT dc.challenge_date, a.wiki_pageid, a.display_title, c.id, c.clue_text FROM daily_challenges dc "
            f"JOIN articles a ON a.id = dc.article_id JOIN clues c ON c.article_id = a.id "
            f"WHERE dc.challenge_date >= '{args.from_date}' AND (c.clue_type = 'creation_year' OR c.clue_text LIKE '%was created in%');"
        )
        # Keyed by pageid, not by this database's clue ids, since ids in
        # production needn't match the local ones. The clue_type/text guards
        # make each statement a no-op on an already-fixed clue.
        for pageid, (new_type, new_text) in REPLACEMENTS.items():
            print(
                f"UPDATE clues c JOIN articles a ON a.id = c.article_id "
                f"SET c.clue_type = {_sql_literal(new_type)}, c.clue_text = {_sql_literal(new_text)} "
                f"WHERE a.wiki_pageid = {pageid} AND (c.clue_type = 'creation_year' OR c.clue_text LIKE '%was created in%');"
            )
        return 0

    with session_scope() as session:
        rows = (
            session.query(Clue, Article, DailyChallenge.challenge_date)
            .join(Article, Clue.article_id == Article.id)
            .join(DailyChallenge, DailyChallenge.article_id == Article.id)
            .filter(DailyChallenge.challenge_date >= args.from_date)
            .order_by(DailyChallenge.challenge_date)
            .all()
        )
        stale = [(c, a, d) for c, a, d in rows if is_stale_creation_year(c.clue_type, c.clue_text)]

        missing = [(c, a, d) for c, a, d in stale if a.wiki_pageid not in REPLACEMENTS]
        if missing:
            for clue, article, day in missing:
                print(f"MISSING: {day} {article.display_title} (pageid {article.wiki_pageid}, clue {clue.id}): {clue.clue_text!r}", file=sys.stderr)
            print("ABORT: add replacements for the clues above; nothing written.", file=sys.stderr)
            return 1

        for clue, article, day in stale:
            new_type, new_text = REPLACEMENTS[article.wiki_pageid]
            if leaks_title(new_text, article):
                print(f"ABORT: replacement for {article.display_title} leaks its title; nothing written.", file=sys.stderr)
                return 1

        for clue, article, day in stale:
            new_type, new_text = REPLACEMENTS[article.wiki_pageid]
            old_type = clue.clue_type
            clue.clue_type = new_type
            clue.clue_text = new_text
            print(f"OK: {day} clue {clue.id} ({article.display_title}) {old_type} -> {new_type}")

        if not stale:
            print(f"Nothing to do: no stale creation-year clues from {args.from_date} onward.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
