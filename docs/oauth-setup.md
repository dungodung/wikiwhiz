# Registering a Wikimedia OAuth 2.0 consumer

WikiWhiz logs users in via Wikimedia's Central Auth (the same account used
across Wikipedia, Wikidata, Commons, etc.), so anyone with a Wikimedia
account can log in without creating a separate WikiWhiz account. This step
is **manual** and must be done by the maintainer (it requires your own
Wikimedia account) — Claude Code cannot do this for you.

## Steps

1. Go to <https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose>
   while logged into your Wikimedia account.
2. Choose **OAuth 2.0**, "This consumer is for use in a web application"
   (not owner-only).
3. Fill in:
   - **Application name**: `WikiWhiz` (or `WikiWhiz (dev)` for the local
     development consumer — register two separate consumers, one per
     callback URL, since a consumer maps to one callback).
   - **Description**: a short description of the game.
   - **Callback URL**:
     - dev consumer: `http://localhost:5000/api/auth/callback`
     - prod consumer: `https://wikiwhiz.toolforge.org/api/auth/callback`
   - **Applicable project**: "all projects" (so any Wikimedia account works,
     not just en.wikipedia.org accounts).
   - **Grants**: identity only — WikiWhiz never edits anything, so no edit
     rights are needed. Look for the minimal "basic rights"/identity grant.
4. Submit. Approval for a non-owner-only consumer can take some time
   (reviewed by OAuth admins) — start this early, it doesn't block any other
   milestone.
5. Once approved, you'll have a **Client ID** and **Client secret**. Set them:
   - Locally: in `.env`, as `WIKIWHIZ_OAUTH_CLIENT_ID` /
     `WIKIWHIZ_OAUTH_CLIENT_SECRET` (and `WIKIWHIZ_OAUTH_REDIRECT_URI` to
     match the dev callback above).
   - In production: via `toolforge env set` (see `deployment-toolforge.md`).

## How it's used in code

`backend/app/blueprints/auth/oauth_client.py` implements the Authorization
Code flow against `meta.wikimedia.org/w/rest.php/oauth2/*`:
`/api/auth/login` redirects to Wikimedia's authorize endpoint with a random
`state`; `/api/auth/callback` validates that `state` (CSRF protection),
exchanges the code for an access token, fetches the user's profile, and
upserts a `User` row keyed by the profile's `sub`. The access/refresh tokens
are never stored — see `docs/db-schema.md`.
