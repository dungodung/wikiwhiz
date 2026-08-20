# WikiWhiz architecture

See the plan this was built from for full rationale:
`~/.claude/plans/i-want-to-create-idempotent-pascal.md` (or ask Claude Code
to recall it). This doc is the living summary.

## Stack

- **Backend**: Flask (app factory in `backend/app/__init__.py`), SQLAlchemy
  ORM (`backend/app/models/`), Alembic migrations (`backend/migrations/`).
- **Frontend**: React 19 + Vite, `react-router-dom`, Zustand for state
  (`frontend/src/`).
- **Database**: MySQL/MariaDB (local via `docker-compose.yml`, production via
  Toolforge ToolsDB).
- **Auth**: Wikimedia OAuth 2.0 Authorization Code flow
  (`backend/app/blueprints/auth/`), identity only — no tokens persisted.
- **Deployment**: Toolforge Build Service. See `deployment-toolforge.md`.

## Request flow

`GET /api/game/today` and `POST /api/game/guess`
(`backend/app/blueprints/game/routes.py` → `service.py`) are the entire game
surface. Identity is either a logged-in `user_id` (Flask session cookie) or
an anonymous UUID (`wikiwhiz_anon` cookie, set on first visit). A
`GameSession` row is only ever created on the first submitted guess
(`service.get_or_create_session`, called from the guess routes) -- viewing a
puzzle is read-only (`service.get_session`, called from the state routes),
so idle visitors who never actually play leave no database row behind. When
no session exists yet, `serialize_state` renders the same fresh starting
state (first clue only, no guesses) a brand-new session would have, just
without one backing it.

**A guess is a filled-in tile board, not free text.** `Article.slot_pattern`
(`lib/slot_pattern.py`) is a flat string over the whole title: `'L'` per
guessable letter tile, and every other character (space, dash, comma,
parenthesis) is its own fixed, revealed tile — structural, never hidden or
guessable, but never discarded either. All other punctuation (quotation
marks, periods, colons, apostrophes, digits) and diacritics (transliterated
to ASCII first) are stripped before the shape is computed. `guess_text` sent
to `/guess` must already be exactly this length, letters where the pattern
says `'L'` and the exact fixed character everywhere else;
`service.check_guess_shape` rejects (400) anything else before it's scored.

Each guess:
1. Checked for an exact match against `normalize_to_tiles(article.display_title)`
   (case-insensitive) — this alone decides win/loss, no network call.
2. Scores lexical closeness (`lib/similarity.py`) against the same flat
   answer-tile string — always available, no network dependency.
3. If not a win, resolved via `service._resolve_wrong_guess`: first a local,
   indexed lookup in `lib/degrees.py` against `LinkCacheNode` by
   `(answer_article_id, node_tiles)`, which returns both which real article
   the guess spells out and its precomputed hop-distance in one query; on a
   cache miss, a live best-effort check (`lib/hint_search.py::verify_real_article`)
   confirms the guess is *some* real enwiki article (an exact title/redirect
   lookup first, then a sliding-window CirrusSearch fallback) before it's
   allowed to count as an attempt at all — see "Guess validation" below.
   A guess that resolves via cache **degrades to "not found nearby"** for
   degrees (no live BFS is ever attempted) rather than failing the request.
4. Records a `GuessAttempt`, advances `GameSession` (reveal next clue / win /
   lose), and updates `UserStats` if logged in.

The candidate pool `LinkCacheNode` rows are drawn from is populated ahead of
time by `scripts/precompute_link_cache.py`, which BFS-walks the real
Wikipedia link graph outward from the answer and keeps only same-**total-
tile-count** neighbors (any other length could never fill this answer's
board anyway — see "Post-launch additions" below for why length-only,
not exact shape).

## Content pipeline

Content (articles + clue sets) is authored ahead of time, not generated at
request time. See `.claude/skills/wikiwhiz-content-author/SKILL.md` — a
human-invoked Claude Code skill that walks through candidate selection, clue
sourcing, and calls the `scripts/db_*.py` helpers (never raw SQL) to insert
rows through the same validation gates (duplicate check, title-leak guard,
minimum-clue-count gate) every time.

`scripts/check_pool_level.py` runs daily (cron) and emails the maintainer
once when the scheduled-but-unplayed day count drops to `LOW_POOL_THRESHOLD`
(default 3) — see `lib/notifications.py` and `models/pool_alert.py`.

## Post-launch additions

- **Archive/replay**: `GET /api/game/archive`, `/api/game/day/<date>`,
  `POST /api/game/day/<date>/guess` reuse the same `game_sessions`/
  `guess_attempts` tables (already keyed by daily_challenge_id, not date).
  `service.process_guess` only calls `_update_user_stats` when
  `daily_challenge.challenge_date == today` — replaying an old day never
  touches streaks/win_distribution.
- **Hint mode**: `GET /api/game/day/<date>/hint?pattern=...`
  (`backend/app/lib/hint_search.py`). Player fills in any subset of letter
  tiles, in any order; the server builds a plain `intitle:"..."` CirrusSearch
  keyword query from the longest known literal run to fetch ~50 candidates,
  then **locally re-verifies every candidate** by running it through the same
  `normalize_to_tiles()` used for the answer and checking a regex built from
  the puzzle's `slot_pattern` before returning anything. This two-step design
  exists because CirrusSearch's documented `intitle:/regex/` feature did *not*
  reliably filter to the regex in live testing against production
  en.wikipedia.org (returned titles that plainly didn't match) — see the
  regression test `test_search_locally_filters_out_noisy_candidates` in
  `backend/tests/test_hint_search.py`. Each match returned includes both the
  real `title` (for display) and its `tiles` form (for the client to fill the
  board directly on click, with no client-side normalization needed).
- **Admin panel**, gated by `User.is_admin` (bootstrap the first admin via
  `scripts/promote_admin.py --username <name>`, after they've logged in once
  — there's no other way to create the first admin). All mutations under
  `/api/admin/*` (`backend/app/blueprints/admin/routes.py`) are blocked once
  an article's daily_challenge date is today or in the past
  (`_article_is_locked`), so nothing a player has already seen can change
  underneath them. Shares its title-leak guard and scheduling logic with the
  CLI scripts via `lib/clue_guard.py` / `lib/scheduling.py`.
- **Tile-based guessing (replaced free-text guesses)**: guesses are now
  filled in directly on the tile board (see "Request flow" above) instead of
  typed as free text and resolved via a live MediaWiki search. This removed
  `lib/resolve.py` and the `title_resolutions` table entirely, and changed
  what `scripts/precompute_link_cache.py` keeps: only same-total-tile-count
  neighbors are written to `link_cache_nodes`, each carrying a `node_tiles`
  column (its own normalized tile string) that `lib/degrees.py` looks guesses
  up by directly. Deliberately **length-only**, not exact-shape matching, for
  what counts as a precompute candidate — a submitted guess still has to
  match a cached node's tiles exactly to resolve, but the precompute casts a
  looser net so more real articles are eligible candidates in the first
  place, per the request that motivated this: "gives more opportunities for
  other articles to match just the number of letters in total." An earlier
  iteration of this redesign hid word boundaries entirely (only total
  letter+dash count shown); that was reversed after further feedback — see
  the next bullet.
- **Word boundaries are shown, not hidden**: `lib/slot_pattern.py`'s
  `KEPT_PUNCTUATION = " -,()"` keeps space, dash, comma, and parentheses as
  their own fixed, revealed tiles — structural, but never hidden or
  discarded — while all other punctuation and diacritics are stripped as
  before. Because a submitted guess therefore already carries the answer's
  real spacing, most correct guesses now resolve via a direct exact-title
  lookup rather than needing search-based reconstruction at all.
- **Guess validation against real enwiki articles**: a wrong guess only
  counts as an attempt if it spells some real English Wikipedia article —
  gibberish is rejected (422, no `GuessAttempt` recorded, clue not advanced)
  by `service._resolve_wrong_guess`, which falls back to
  `lib/hint_search.py::verify_real_article` on a `LinkCacheNode` cache miss.
  That function tries `client.resolve_title` first (an exact lookup that
  follows redirects, so a common alternate name or concatenated-no-space
  variant still counts as real — deliberately not discarded), then falls
  back to a sliding-window CirrusSearch recall (multiple substring windows,
  many sizes, OR-combined into one query) plus local `normalize_to_tiles()`
  verification if the direct lookup misses. A live-search failure degrades
  to accepting the guess unresolved (no degrees) rather than blocking play;
  it will never *accept* a fake title, only occasionally fail to *confirm* a
  real one if none of the tried windows happen to land on a real word.
  Hint mode's own candidate-recall query was similarly broadened
  (`intitle:"run" OR "run"`) so a known letter run that spells a redirect's
  title also surfaces the real target article as a suggestion.
- **Wiki Replicas as the preferred degrees-of-Wikipedia backend**: since
  wikiwhiz deploys to Toolforge, `lib/degrees.py::compute_degrees_live` and
  `scripts/precompute_link_cache.py` now call `lib/wiki_replica.get_client()`
  once per invocation and, if it returns a client, run the same BFS against
  a direct SQL connection to Wikimedia's read-only Wiki Replicas
  (`pagelinks`/`linktarget`/`page`, via `~/replica.my.cnf`, auto-provisioned
  per-tool on Toolforge) instead of the paginated MediaWiki Action API — a
  single indexed JOIN vs. potentially hundreds of sequential HTTP calls for
  a hub-like article. `get_client()` never raises; it returns `None` on any
  failure (missing cnf file, unreachable host, auth failure, timeout), so
  the live-API `MediaWikiClient` path — the only path that ever runs locally,
  since the replica hosts aren't reachable outside Wikimedia Cloud VPS — is
  unchanged and remains the fallback. The BFS itself doesn't know which
  backend it's using: `MediaWikiClient` and `WikiReplicaClient` both
  implement the same duck-typed `links_batch`/`linkshere_batch`/
  `titles_to_pageids`/`pageids_to_titles` shape (the latter two extracted
  from title/pageid-resolution code that used to be duplicated inline in
  three places). No mid-run failover between backends: a replica that
  connects but then fails mid-BFS degrades the same way a live-API failure
  always has (`degrees=None, capped=True`), rather than silently retrying
  the whole bounded search against the other backend.

## What's implemented vs. what's next

Implemented and tested (backend unit tests + a live end-to-end HTTP smoke
test against the real Wikipedia API, see below): DB schema, full game loop
(clue reveal, lexical scoring, degrees with graceful network-failure
fallback, win/loss), OAuth routes (untested against a real consumer — needs
one registered, see `oauth-setup.md`), stats, all content-authoring helper
scripts (argument parsing verified; full DB round-trip needs a live
MySQL/MariaDB — this dev sandbox had neither Docker nor a local MySQL server
installed, so `make dev-db` needs to be run on a machine that has Docker
before the content-authoring skill can actually write content), frontend
(builds cleanly, dev server boots, all components wired to the real API
contract).

Not yet done: running the content-authoring skill for a real batch (needs
the local DB up), OAuth consumer registration (manual, needs the
maintainer's Wikimedia account), any Toolforge deployment steps (needs
Toolforge account access), visual/UX polish pass (M4), GitLab CI validation
(the workflow is written but hasn't run against a real GitLab pipeline).
