# WikiWhiz

A public, Wordle-style daily guessing game built on English Wikipedia, Wikidata,
Wikimedia Commons, and Wiktionary content. Guess the day's Wikipedia article from
a series of randomized clues; each guess shows how lexically close you are and
how many "degrees of Wikipedia" (link-hops) separate your guess from the answer.

- Anonymous play supported; log in with your Wikimedia account (OAuth 2.0) to
  keep stats across days.
- Daily challenge resets at 00:00 UTC.
- Content (articles + clue sets) is authored ahead of time via the
  `wikiwhiz-content-author` Claude Code skill — see `.claude/skills/wikiwhiz-content-author/SKILL.md`.

See `docs/architecture.md` for the full design, `docs/db-schema.md` for the
database schema, `docs/oauth-setup.md` for registering an OAuth consumer, and
`docs/deployment-toolforge.md` for the GitLab → Toolforge deployment runbook.

## Local development

```bash
cp .env.example .env
make dev-db
make migrate
make dev-up
```

Then, from Claude Code in this repo, invoke the `wikiwhiz-content-author` skill
to seed the local database with playable articles, and open http://localhost:5173.

Production-shape smoke test (prebuilt frontend served by Flask, no Vite):

```bash
make prod-smoke-test
```
