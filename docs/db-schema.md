# WikiWhiz database schema

Canonical source of truth is `backend/app/models/`; this is a human-readable
summary. Generate/apply migrations with `flask db migrate` / `flask db
upgrade` (see README.md). All tables are InnoDB/utf8mb4.

| Table | Purpose |
|---|---|
| `articles` | The answer pool. `status`: draft → ready → scheduled (→ retired). `slot_pattern` (JSON) is the Wheel-of-Fortune rendering data, computed once at insert time. |
| `clues` | 1 article : many clues. `clue_type` is one of the 14 types in `models/clue.py::CLUE_TYPES`. `is_title_leaking` is a guard flag (should always end up `False` for anything actually used — `db_add_clue.py` refuses to insert a leaking clue). |
| `daily_challenges` | One row per UTC calendar day. `clue_order` (JSON) is the frozen, pre-randomized list of clue ids for that day — request handlers never re-randomize. |
| `link_cache_nodes` / `link_cache_meta` | The degrees-of-Wikipedia precomputed neighborhood cache per answer article, plus live-BFS-discovered nodes written back opportunistically. |
| `title_resolutions` | Global cache: normalized free-text guess → resolved Wikipedia article. Independent of which answer article is being played. |
| `users` | Wikimedia identity only (`wikimedia_sub`, `wikimedia_username`, `is_admin`). No OAuth tokens stored. First admin is bootstrapped via `scripts/promote_admin.py`. |
| `game_sessions` | One per (identity, daily_challenge) pair — identity is either `user_id` or an anonymous cookie token. |
| `guess_attempts` | Every guess ever made, with its scored lexical bucket and degrees result. |
| `user_stats` | Aggregated per-user stats, including `win_distribution` (JSON, e.g. `{"1": 2, "3": 1, "failed": 1}`). |
| `pool_alert_state` | Single-row table tracking whether a low-content-pool email alert is currently "open" (see `scripts/check_pool_level.py`). |

## Notes on design choices

- **Integer, not BigInteger, primary keys.** SQLite (used for the backend
  test suite) only gives `INTEGER PRIMARY KEY` its special autoincrement
  rowid-alias behavior, not `BIGINT` — using `BigInteger` broke inserts
  under SQLite while working fine under MySQL, which would have meant an
  untested code path. `Integer` (32-bit) is enormously more headroom than
  this app will ever need and keeps the model portable across both
  dialects.
- **`clue_order` and `win_distribution` are JSON columns**, not normalized
  tables or fixed columns, specifically so the clue-count range (5-7) or
  scoring details can change later without a migration touching historical
  rows.
- **No OAuth tokens are persisted anywhere.** The app only needs identity,
  not delegated API access on the user's behalf, so access/refresh tokens
  are used transiently during the `/api/auth/callback` request and
  discarded.
