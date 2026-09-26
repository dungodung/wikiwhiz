---
name: wikiwhiz-content-author
description: Use when the user asks to generate new WikiWhiz daily-challenge content, expand or top up the WikiWhiz article/clue pool, seed a fresh WikiWhiz database with playable puzzles, or respond to a WikiWhiz "low content pool" alert email. Human-invoked only — never run this unattended or on a schedule; the user always kicks off an invocation and reviews the summary at the end.
---

# WikiWhiz content author

Selects good candidate English Wikipedia articles, gathers a 7-clue set for
each spanning several clue types, precomputes the degrees-of-Wikipedia link
cache, and schedules each article onto the next open daily-challenge date.
Everything is written through the helper scripts in `scripts/` — never write
raw SQL by hand — so the schema stays a single source of truth and every
insert goes through the same validation gates (duplicate check, title-leak
guard, minimum-clue-count gate) regardless of who or what is calling them.

Default batch size is **10 articles** for a first invocation on an empty
pool. For a top-up run (e.g. responding to the low-pool alert email from
`scripts/check_pool_level.py`), ask the user how many to add if they didn't
say, or default to enough to bring the schedule back to a few weeks of
runway.

Before starting, confirm `.env` is configured (`DB_*`, `WIKIWHIZ_USER_AGENT`)
and scripts are run from the repo root with the venv active, e.g.:
`source .venv/bin/activate && python3 scripts/db_add_article.py --help`

## Workflow (repeat per article until the batch count is reached)

1. **Load the existing pool** to avoid duplicates and get a feel for recent
   topics/difficulty spread:
   `python3 scripts/db_check_duplicate.py --list-existing`

2. **Pick a candidate article.** See `references/candidate_criteria.md` for
   the full selection rubric (prefer Featured/Good articles, length,
   infobox, images, Wikidata richness, editorial exclusions). Once you have
   a title, get its pageid and confirm it's not already in the pool:
   `python3 scripts/db_check_duplicate.py --title "Article Title"`
   If it returns `DUPLICATE`, pick a different candidate.

3. **Insert the article** (status starts as `draft`):
   `python3 scripts/db_add_article.py --title "..." --pageid N --display-title "..." --summary "..." `
   Note the returned `article_id`.

4. **Gather material for each clue type** by querying the matching Wikimedia
   API/skill — see `references/candidate_criteria.md` for which endpoint
   covers which clue type (Commons `Special:FilePath`, Wikidata
   `wbgetentities`, infobox parse, smallest-size categories, Wiktionary
   etymology, Wikisource excerpt, Wikivoyage fact, pageviews REST endpoint,
   top citation, `linkshere` count, longest section title, plus
   `creation_year`/`langlinks_count` as low-leakage fallbacks when a type
   doesn't apply). **Facts before stats, as a hard rule, not a preference**
   — see `references/candidate_criteria.md`'s "Facts before stats" section:
   exhaust the fact types (categories, sections, DYK, Wikidata, infobox,
   etymology, images, citations, Wikisource, Wikivoyage) before reaching for
   any stat type (link counts, edit/editor counts, language count, creation
   year) at all, and cap stats at one per article. Not every type applies to every
   article — that's fine, see step 6.

5. **Draft clue text** for each fact per `references/clue_style_guide.md`
   (tone, length, how obscure vs. revealing each type should read). Before
   inserting, mentally check the draft doesn't contain the article's title
   or an obvious redirect as a substring — but don't rely on this alone,
   step 6's script enforces it as a hard gate.

6. **Insert each clue:**
   `python3 scripts/db_add_clue.py --article-id N --type CLUE_TYPE --text "..." --reveal-rank-hint R [--media-url URL] [--payload-json '{...}']`
   If this is rejected for leaking the title, redraft the text and retry —
   do not try to bypass the guard. `--reveal-rank-hint` is 1 (obscure, shown
   early) to 7 (revealing, shown late); see the style guide for defaults per
   clue type.

7. **Reach exactly 7 valid clues — this is the target, not a range.** The
   `--set-status ready` gate in step 9 only enforces >=5, so it will happily
   let a 6-clue article through; that is not good enough and has had to be
   backfilled after the fact. Keep going until there are 7. If fewer than 7
   of the "applicable" types panned out, add an extra fact-based clue (a
   second Wikidata statement, a second category/section fact, `creation_year`,
   or `langlinks_count`) rather than forcing a weak or leaky clue into an
   inapplicable type. Verify with
   `SELECT COUNT(*) FROM clues WHERE article_id = N` before moving on.

8. **Precompute the degrees-of-Wikipedia cache — via the Wiki Replica, not
   the API:**
   `python3 scripts/precompute_link_cache.py --article-id N`
   (defaults: depth 4, node cap 3000 — use these, don't reduce them).

   The script prints which link source it chose. It **must** say
   `Link source: Wiki Replicas (SQL)`. If it says
   `MediaWiki API (fallback)`, stop and fix the replica path first rather
   than proceeding — the API path is for when the replica is genuinely
   unreachable, not a normal choice. It's hundreds of sequential paginated
   HTTP calls instead of one indexed JOIN, and in practice it stalls out on
   well-linked articles and yields a degraded cache.

   `wiki_replica.get_client()` picks the replica whenever `replica.my.cnf`
   exists and the replica host is reachable, and honors
   `WIKI_REPLICA_CNF_PATH` / `WIKI_REPLICA_HOST` / `WIKI_REPLICA_PORT`.
   From a dev machine (where neither is true by default), tunnel through the
   Toolforge bastion and point those env vars at the local end:
   ```
   ssh -f -N -L 4711:enwiki.analytics.db.svc.wikimedia.cloud:3306 <you>@login.toolforge.org
   # replica.my.cnf lives at /data/project/wikiwhiz/replica.my.cnf on the
   # bastion; copy it somewhere local with 0600 perms (it's a credential)
   export WIKI_REPLICA_CNF_PATH=/path/to/local/replica.my.cnf
   export WIKI_REPLICA_HOST=127.0.0.1
   export WIKI_REPLICA_PORT=4711
   ```

9. **Promote to ready** (the script's own gate is only >=5 non-leaking clues
   — step 7's 7-clue target is the real bar):
   `python3 scripts/db_add_article.py --set-status ready --article-id N`

10. **Schedule it** onto the next open UTC date:
    `python3 scripts/db_schedule_challenge.py --article-id N --next-available`

11. Move to the next candidate. When the batch count is reached, **print a
    summary table** (article, scheduled date, clue types used, any
    warnings) so the user can spot-check before playing.

## After a batch

Mention to the user that they can spot-check content quality by playing
through a few of the newly-scheduled days locally, and that
`scripts/db_export_pool.py --since-id <watermark>` is how new content gets
promoted to production once reviewed (see `docs/deployment-toolforge.md`) —
this skill only ever writes to whichever database `.env` points at (local by
default), never directly to production.
