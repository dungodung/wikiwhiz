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
`GameSession` row is created lazily per (identity, daily_challenge) pair.

Each guess:
1. Resolves free text to a real article (`lib/resolve.py`, cached in
   `title_resolutions`).
2. Scores lexical closeness (`lib/similarity.py`) — always available, no
   network dependency.
3. Looks up degrees-of-Wikipedia (`lib/degrees.py`) — cache hit is instant;
   cache miss runs a bounded live BFS with a hard timeout/node cap, and
   **degrades to "not found nearby" rather than failing the request** if the
   MediaWiki API is unreachable or rate-limited (this really happens — see
   the regression test `backend/tests/test_degrees.py`).
4. Records a `GuessAttempt`, advances `GameSession` (reveal next clue / win /
   lose), and updates `UserStats` if logged in.

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
