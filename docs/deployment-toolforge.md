# GitLab → Toolforge deployment runbook

WikiWhiz deploys to Wikimedia Toolforge via **Build Service** (git push
triggers an automatic container build), not the traditional rsync-based
Kubernetes backend. This matters because Build Service images support only
one primary language runtime per image — the Python buildpack can't also run
`npm run build` — so the React frontend is always built to static assets
*before* the repo is pushed for a Toolforge build, never during it.

## One-time setup

1. **Register OAuth consumer(s)** — see `oauth-setup.md`. Start this early;
   approval isn't instant and doesn't block anything else here.
2. **Create the Toolforge tool** (from `login.toolforge.org`, requires an
   approved Toolforge account):
   ```
   toolforge tools create wikiwhiz
   toolforge tools maintainers add wikiwhiz <your-username>
   ```
3. **Provision ToolsDB** (the tool's own writable MariaDB, separate from the
   read-only wikireplica databases):
   ```
   become wikiwhiz
   sql wikiwhiz
   ```
   Record the connection details (host is `tools.db.svc.wikimedia.cloud`;
   credentials come from `replica.my.cnf` in the tool's home directory).
4. **Create the GitLab repo** at
   `gitlab.wikimedia.org/toolforge-repos/wikiwhiz` (via the Toolforge tool
   dashboard, which provisions this automatically) and add it as a remote.

## The `deploy` branch

`main` never contains built frontend assets (`frontend/dist/`,
`backend/app/static/*` are gitignored). `.gitlab-ci.yml` builds the frontend
and force-pushes the result onto a `deploy` branch on every push to `main`
— that branch is what Toolforge actually builds from. To do this manually
instead of relying on CI:
```
./scripts/build_frontend.sh
git checkout -B deploy
git add -f backend/app/static
git commit -m "deploy: rebuild frontend"
git push origin deploy -f
```

## Deploying / redeploying

```
# one-time env var setup (repeat if a value changes)
become wikiwhiz
toolforge env set SECRET_KEY "..."
toolforge env set WIKIWHIZ_OAUTH_CLIENT_ID "..."
toolforge env set WIKIWHIZ_OAUTH_CLIENT_SECRET "..."
toolforge env set WIKIWHIZ_OAUTH_REDIRECT_URI "https://wikiwhiz.toolforge.org/api/auth/callback"
toolforge env set DB_HOST "tools.db.svc.wikimedia.cloud"
toolforge env set DB_NAME "wikiwhiz"
toolforge env set DB_USER "..."
toolforge env set DB_PASSWORD "..."
toolforge env set WIKIWHIZ_USER_AGENT "WikiWhiz/1.0 (https://wikiwhiz.toolforge.org) requests"
toolforge env set MAINTAINER_EMAIL "your-address@example.org"
toolforge env set MAIL_FROM "wikiwhiz@toolforge.org"
toolforge env set SMTP_HOST "mail.tools.wmcloud.org"

# run migrations against ToolsDB (from a shell with the tool's env, or via `toolforge jobs run`)
flask --app wsgi db upgrade

# build & start
toolforge build start https://gitlab.wikimedia.org/toolforge-repos/wikiwhiz --ref deploy
toolforge build show   # wait for "ok (Succeeded)"
toolforge webservice buildservice start --mount=none
```

Redeploy after a code change: push `main`, let CI (or the manual steps
above) update `deploy`, then re-run `toolforge build start` +
`toolforge webservice buildservice restart`.

## Verify

- `https://wikiwhiz.toolforge.org/` loads the game.
- `https://wikiwhiz.toolforge.org/api/game/today` returns a puzzle (once
  content has been scheduled — see below).
- OAuth round-trip: log in, confirm the username shows up, log out.

## Scheduling the low-pool alert cron job

```
become wikiwhiz
toolforge jobs schedule check-pool-level \
  --command "/data/project/wikiwhiz/venv/bin/python3 /data/project/wikiwhiz/scripts/check_pool_level.py" \
  --schedule "10 0 * * *" \
  --image python3.12
```
Run it once manually first to confirm mail actually reaches
`MAINTAINER_EMAIL` before relying on the schedule.

## Getting content onto production

Content is **authored locally** (where Claude Code runs — invoke the
`wikiwhiz-content-author` skill against your local `.env`/database) and
**reviewed before promotion**, rather than the skill ever running directly
against production. To promote a batch:
```
python3 scripts/db_export_pool.py --since-id <last-synced-article-id> > /tmp/pool_export.sql
TOOLFORGE_USER=you DB_USER=... DB_PASSWORD=... scripts/sync_pool_to_prod.sh /tmp/pool_export.sql
```
Track the watermark (the highest `articles.id` you've synced) yourself
between runs — there's no separate table for it, it's just "the last id you
passed to `--since-id` last time."
